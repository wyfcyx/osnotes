# 1. 入门

## 1.1 为何选择异步

* 线程模型很好，可以利用多核资源同时完成多项任务
* 但是线程切换带来很大的上下文切换开销；同时线程间的同步互斥开销也很大
* 考虑将多线程换成异步实现，这可能使得运行速度更快且占用更少的资源
* 但问题在于异步不像是线程模型那样有着 OS 的原生支持，需要语言或库的特别支持
* 需要记住：基于传统线程模型的应用也可以做到很高效，并在 Rust 的支持下可靠且安全；使用异步模型代替线程模型不总是更好的，这取决于具体应用环境

## 1.2 异步 Rust 语法

* 目前稳定化的语法：`Future` trait + `async/.await`
* 该特性仍在高速开发中，目前使用的是 `0.3` 版本

## 1.3 初识 `async/.await` 

* `async` 将一个代码块转化为一个实现了 `Future TO(Trait Object,下同)` 的状态机

  虽然状态机的状态和转移都不清楚，但是状态机就是状态机！

* 我们知道，在同步实现中调用一个阻塞函数，整个线程都会被阻塞；但在异步 Rust 实现中，被阻塞的 `Future` 将交出线程的控制权，并允许其他 `Future` 运行

* 异步函数声明应使用 *async fn*，其返回值是一个 `Future`

* 声明异步函数之后只是创建了状态机，还需要把它丢到 `Executor` 中去调度、执行。如 *futures::executor::block_on*，作用是阻塞当前线程直到给定的 `Future` 运行完毕。不同的 `Executor` 机制不同，可以在同一线程上调度多个 `Future` 并发执行。

* 在一个 *async fn* 块内部，可以使用 *.await* 来异步等待另一个 `Future` 执行完毕，它并不会阻塞当前线程；注意我们可以使用 *.await* 建立异步任务之间的拓扑关系

* 而 *futures::join!* 可以并发等待多个 `Future` 完成，一旦其中某个被阻塞，其他 `Future` 将获取线程使用权；如果所有 `Future` 全被阻塞，那么这个整体的 `Future` 将被阻塞并将控制权移交

## 1.4 应用：异步 Http 服务器

# 2. 执行 `Future` 与任务

* 这一章主要介绍 `Future` 的调度原理以及 *async/.await* 的底层架构

## 2.1 `Future` Trait

* `Future` 描述一段可以输出一个值的异步计算过程

* 最简单的 `Future`

  ```Rust
  trait SimpleFuture {
      type Output;
      // 输出的类型
      fn poll(&mut self, wake: fn()) -> Poll<Self::Output>;
      // 通过 poll 来尝试获取 Future 的计算结果
      // 如果该 Future 已经计算完成，那么会直接返回 Poll::Ready 以及计算结果
      // 如果未计算完成，那么会直接返回 Poll::Pending ，且当该 Future 的进度继续推进时，将会调用 wake 函数，这会告诉 Executor 是时候重新 poll 一下了
  }
  
  enum Poll<T> {
      Ready(T),
      Pending,
  }
  ```

* *wake* 函数的作用：`Executor` 需要通过 *wake* 知道一个特定的 `Future` 执行进度何时开始增长并需要重新 *poll*

* `Future` 模型允许将多个异步计算过程合成一个而不需要任何中间状态。立即同时运行多个 `Future` 或者将多个 `Future` 连接在一起可以用无需分配的状态机来实现。后面给出了一段代码，可以将两个 `Future` 组合成一个大的 `Future`，在大的 `Future` 的 *poll* 函数中，依次调用子 `Future` 的 *poll* 函数来更新整体的状态。这是二者并列的情形，如果是有严格的先后顺序的话也很容易实现。事实上，它们的实现并不需要多重分配对象或是深层嵌套的回调函数。

* 而实际上的 `Future` 模型中的 *poll* 的函数签名要更加复杂：

  ```rust
  fn poll(
      self: Pin<&mut Self>, // 从 &mut self 变更而来
      cx: &mut Context<'_>, // 从 wake: fn() 变更而来
  ) -> Poll<Self::Output>;
  ```
  
  我们目前不需要对于 Pinning 有过多了解，只需知道它允许我们创建*不可移动*的 `Future`，所谓的“不可移动”指的是在字段中可以包含指针。对于实现 *async/.await* 来说，这就已经足够了。
  
  而原来用于通知 `Executor` 对应的 `Future` 需要重新 *poll* 的 *wake* 函数也被替换，这是因为 *fn()* 只是一个函数指针，并不能包含有关是哪个 `Future` 调用了 *wake* 函数的信息。在真实应用中，一个服务器可能需要需要分别管理数千个不同的连接。而 `Context` 类型通过访问一个 `Waker` 类型的值来解决这个问题。`Waker` 可以用来唤醒一个特定的任务。
## 2.2 通过 `Waker` 唤醒任务

* 当一个 `Future` 第一次被 *poll* 的时候还未完成是很常见的情况。这时，它就需要保证一旦它准备好继续干活，就需要再次被 *poll*。这是通过 `Waker` 来实现的。
* 每当一个 `Future` 被 *poll* 的时候，实际上它是作为一个“任务 (Task)”的一部分被 *poll* 的。已经被提交给一个 `Executor` 的上层 `Future` 被称为一个任务。
* `Waker` 提供一个可以用来告诉 `Executor` 相关的任务需要被唤醒的 *wake* 函数。当 *wake* 函数被调用的时候，`Executor` 知道与该 `Waker`  相关的任务准备继续干活，从而它对应的 `Future` 需要被重新 *poll*。`Waker` 还实现了 *clone* 函数。 

**应用：计时器**

* 考虑一个小例子，我们在计时器创建的时候将一个新线程睡眠一段指定长度的时间，并在这之后提醒计时器 `Future`。

* 首先是计时器 `Future` 本身：

  ```rust
  pub struct TimerFuture {
      shared_state: Arc<Mutex<SharedState>>,
  }
  // Future 与被阻塞线程之间共享的状态
  struct SharedState {
      // 睡眠的时间是否过去
      completed: bool,
      // TimerFuture 运行所在的 Waker
      // 一个线程可以通过设置 `completed = true' 来告诉 TimerFuture 对应的任务需要被唤醒
      waker: Option<Waker>,
  }
  ```

* 随后，考虑为 `TimerFuture` 具体实现完整的 *poll* 接口。

  ```rust
  impl Future for TimerFuture {
      type Output = ();
      fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
          let mut shared_state = self.shared_state.lock().unwrap();
          if shared_state.completed {
              Poll::Ready(())
          } else {
              // 设置 Waker 使得当计时完成的时候，线程可以唤醒当前的 Task，保证对应的 Future 可以重新被 poll 并进入 'completed = true' 分支
              // 相比每次都 clone 一个 waker，只做一次看起来更有吸引力。然而，TimerFuture 可以在 Exetutor 的不同 Task 间移动，可能导致一个过期的 waker 指向一个错误的任务，从而 TimerFuture 不能被正确唤醒（事实上可以通过恰当的实现来避免这种情况，但暂时忽略）
              shared_state.waker = Some(cx.waker().clone());
              Poll::Pending
          }
      }
  }
  ```
  
* 注意：每当 `Future` 被 *poll* 的时候，我们必须相应的更新 `SharedState` 中的 waker，原因在于该 `Future` 可能已经被移动到一个不同的任务与不同的 `Waker` 中。这个过程在 `Future` 在被 *poll* 之后被在任务之间作为参数传递的时候将会发生。

* 接下来考虑如何创建一个 `TimerFuture`:

  ```rust
  impl TimerFuture {
      pub fn new(duration: Duration) -> Self {
          let shared_state = Arc::new(Mutex::new(SharedState{
              completed: false,
              waker: None,
          }));
          
          // 创建一个新线程睡眠一段时间并在这之后更新共享状态，并使用 waker.wake() 唤醒对应 Future
          let thread_shared_state = shared_state.clone();
          thread::spawn(move || {
              thread::sleep(duration);
              let mut shared_state = thread_shared_state.lock().unwrap();
              shared_state.completed = true;
              if let Some(waker) = shared_state.waker.take() {
                  waker.wake()
              }
          });
          
          TimerFuture { shared_state }
      }
  }
  ```

  

## 2.3 构造 `Executor`

* Rust 中的 `Future` 是懒惰的，如果没有人驱使它们完成的话它们什么也不会做。一种方式是在 *async fn* 中使用 *.await*，但是这等于是将问题抛给更上一级，谁将负责运行最上层 *async fn* 返回的 `Future` 呢？其实就是 `Executor` 。
* `Executor` 接受一个最上层 `Future` 集合并在其中某个 `Future` 可以继续干活的时候调用 *poll* 函数获取其最新工作进度，直到所有 `Future` 均运行结束。
* 下面我们尝试实际构造一个 `Executor`。`Executor` 的工作原理就是通过通道将任务发出执行。`Executor` 将从通道中获取事件并运行相应的 `Future`。当一个任务被唤醒(准备好开始工作时)，它可以通过将自己放回到通道的方式来调度自己使得自己可以再次被 *poll*。
* 在这个设计中，`Executor` 只需要任务通道的接受端