[here](https://os.phil-opp.com/async-await/#multitasking)

## 抢占式多任务（Preemptive Multitasking）

* Program->Process, Task->Thread

* thread（或者另一种说法 *thread of execution*） 可能在执行任意一条指令的时候被 OS 打断，它必须保存调用栈和当前 CPU 寄存器状态。但是由于栈一般很大，我们给每个 Task 一个独立的栈，就不用保存了。这样大大提高了上下文切换效率。
* 优点：对于 Task 可以完全控制；公平；安全
* 缺点：每个 Task/Thread 必须用独立的栈，占用大量内存；上下文切换需要保存/恢复全部寄存器，但其实它们并没有被全部用到。

## 非抢占式多任务（Cooperative Multitasking）

* 每个 Task 只有主动交出 CPU 使用权才会暂停，*因此它们只会在特定的位置停下来*

* 由于现代 OS 的安全性，它目前只会在编程语言中以协程（coroutine）或异步（async/await） 的形式出现

  由程序员自己或是编译器负责在合适的地方插入 yield

* 非抢占式多任务和异步可以很好地结合。异步意味着并不会等待 I/O 操作返回结果而是会立即返回一个 not ready，在这个时候它就可以被 yield 让其他任务执行。

* 由于一个任务知道自己什么时候被 yield，它可以只保存自己需要的信息而不是当前的所有寄存器状态（注：但不见得开销就会比保存那么多寄存器要小）。作者举了一个例子，就是经过一系列复杂的计算之后，我们可以只用数字节来保存最后的结果。

* 状态，也就是状态机，在 Rust 中应该是以枚举类型的形式保存一个 Future 处于所有可能的状态下被切换出去的时候需要保存的内容（所有接下来能用到的局部变量）。由于是一个枚举类型，它实际消耗的内存是每个状态需要保存的内容大小的最大值。

  出于某种未知的机制，所有的 Future 状态机都是放在一个栈上的。这相比之前（每接收到一个请求开一个新线程处理的方法）为每个 Task 分配一个栈，大大节约了内存，也增加了同时允许的 Task 数目。比较起来的话，就是异步对于每个 Task 只需保存所有状态需要保存的信息的内容的最大值，传统多线程做法的话...

  等等，好像忽然懂了。打一会 Chronicon 来记录一下。

* CPU 控制权主要是在 Executor 和一个 Future 的 poll 调用链之间切换。考虑 Executor poll 一个 Future，它肯定需要在栈上分配一些临时变量，并对这些临时变量进行处理。与此同时，该 Future 应该是存在堆上面的。我们给 poll 传入的参数仅仅是一个 Pin<&mut Self> 而已。也就是说，我们要去堆上查询 Future 上次保存的状态，再加上一个刚刚 Ready 的值（不然就不会 poll 它了），来对临时变量进行计算。然后再次被阻塞的时候，我们将临时变量的值保存在堆上。

  注意到我们 poll 一个 Future 的时候还有可能去 poll 其他的 Future，以此形成一条调用链。

  **这是说，Future 运行时所需的临时变量和 Future 暂停时所保存的状态是两个概念。**
  
  因此，基于 Future 可以使得多条调用链所需的栈空间进行复用，但是代价是要在内存中保存每个 task 的临时状态。那么它和每个 Task 开一个栈究竟孰优孰劣呢？和之前所提到的一样，Future 对于每个 Task 只需在堆中占用各状态所需保存的临时变量大小的最大值，这总是小于栈大小，通常情况下远远小于。
  
  这样仔细想来，相比遇到阻塞就将线程放进一个休眠队列的做法，异步编程会更加方便，且会节省更多内存。
  
  但是上下文保存开销就说不准了。这个完全取决于异步实现中临时变量的数目以及编译器的优化了。这应该是异步性能提升的关键。
  
* 看起来可以分成三层：

  1. 多线程+忙等待
  2. 多线程+阻塞，相比上一层节约更多 CPU 时间
  3. 异步，相比上一层节约更多内存

* 优点：用在编程语言中可以提高性能、降低内存占用；

* 缺点：用在 OS 中会带来潜在风险

## Future poll 接口的使用方法

### 等待

* 直接忙等待，显然不可取
* 即使支持 OS 线程，并阻塞，也依然会让异步任务变成一个同步任务

### 基于 Combinators

* 手动将一个实现了 Future 的类型包装一下，并为新类型实现 Future trait，实际上是在进行 Future 类型的转换
* 优点：包装之后仍然是异步，有着高性能
* 缺点：每个 chain 都需要返回一个相同类型的 Future，由此实现起来相当反人类

## async/await

* 下面演示如何将一段 async fn 转化为一个 Future

  ```rust
  async fn example(min_len: usize) -> String {
      let content = async_read_file("foo.txt").await;
      if content.len() < min_len {
          content + &async_read_file("bar.txt").await
      } else {
          content
      }
  }
  ```

* 其状态机如下：

  ![](https://os.phil-opp.com/async-await/async-state-machine-basic.svg)

  可见一共有四种状态，分别是 Start, End, 还有分别等待在读取 foo.txt 和 bar.txt 的两个状态。

  每个状态需要保存的内容都各不相同。

  我们来看整体的状态设计：

  ```rust
  struct StartState {
      min_len: usize,
  }
  
  struct WaitingOnFooTxtState {
      min_len: usize,
      foo_txt_future: impl Future<Output = String>,
  }
  
  struct WaitingOnBarTxtState {
      content: String,
      bar_txt_future: impl Future<Output = String>,
  }
  
  struct EndState {}
  
  enum ExampleStateMachine {
      Start(StartState),
      WaitingOnFooTxt(WaitingOnFooTxtState),
      WaitingOnBarTxt(WaitingOnBarTxtState),
      End(EndState),
  }
  ```

  可见，我们的确**把子 Future 包裹在大 Future 里面**。因此，在 Executor 看来，它只需管理 top-level 的 Future 即可。当然，实际在 poll 这个 top-level Future 的时候，还会经过一系列的 poll 调用链，接下来就会看到。

  然后我们需要为状态机实现 Future trait：

  ```rust
  impl Future for ExampleStateMachine {
      type Output = String; // return type of `example`
  
      fn poll(self: Pin<&mut Self>, cx: &mut Context) -> Poll<Self::Output> {
          loop {
              match self { // TODO: handle pinning
                  ExampleStateMachine::Start(state) => {…}
                  ExampleStateMachine::WaitingOnFooTxt(state) => {…}
                  ExampleStateMachine::WaitingOnBarTxt(state) => {…}
                  ExampleStateMachine::End(state) => {…}
              }
          }
      }
  }
  ```

  注意我们**将 match 包裹在一个 loop 里面**，这样的话，当 poll 某些子 Future 直接返回 Ready 的时候，我们无须再次 poll top-level Future 就能往下走。接下来，根据当前 Future 所处的状态不同，状态转移也不同：

  Start 状态的任务是将 min_len 参数和接下来要用的 foo.txt Future 传递给下一个状态：

  ```rust
  ExampleStateMachine::Start(state) => {
      // from body of `example`
      // 注意这里只是获取 Future 而并没有去 poll 它，相当于一个懒惰执行
      let foo_txt_future = async_read_file("foo.txt");
      // `.await` operation
      // 生成下一个状态
      let state = WaitingOnFooTxtState {
          min_len: state.min_len,
          foo_txt_future,
      };
      // 更新到下一个状态
      *self = ExampleStateMachine::WaitingOnFooTxt(state);
  }
  ```

  WaitingOnFooTxt 状态的任务如其名，就是在等待 foo.txt。它要做的事情是尝试 poll 一下对应的子 Future，这个子 Future 已经保存在当前的状态中了。然后根据 poll 的结果进行状态转移：

  ```rust
  ExampleStateMachine::WaitingOnFooTxt(state) => {
      match state.foo_txt_future.poll(cx) {
          // 如果子 Future 是 Pending，直接保持原状态不变，下次被唤醒之后再尝试 poll
          Poll::Pending => return Poll::Pending,
          // 如果子 Future 已经完成，准备保存结果并转移到下一个状态
          Poll::Ready(content) => {
              // from body of `example`
              // 原 async fn 的逻辑
              if content.len() < state.min_len {
                  // 如果还需要 bar.txt，类比 Start 生成并保存 Future 到下一个状态
                  let bar_txt_future = async_read_file("bar.txt");
                  // `.await` operation
                  let state = WaitingOnBarTxtState {
                      // 内容也需要保存
                      content,
                      bar_txt_future,
                  };
                  *self = ExampleStateMachine::WaitingOnBarTxt(state);
              } else {
                  // 否则，直接将内容保存到 End 状态并转移
                  *self = ExampleStateMachine::End(EndState));
                  return Poll::Ready(content);
              }
          }
      }
  }
  ```

  由此可以看出，**我们可以对于每个 await 作为状态机中的一个状态，该状态需要保存 await 的那个子 Future，状态转移就是通过尝试 poll 那个子 Future，根据结果进行状态转移。**

  此外，可以发现尝试 poll 子 Future 的时候传进去的那个 cx 是 poll top-level Future 的时候传进来的，因此，**当一个 leaf Future 即将返回 Pending 的时候，它注册的闭包 `cx.waker().wake` 是为了有朝一日在 Executor 唤醒那个 top-level Future，而不是唤醒这个 leaf Future。**这样我们在重新 poll top-level Future 的时候，可以确保进度一定会向前走。

  WaitingOnBarTxt 也是同理：

  ```rust
  ExampleStateMachine::WaitingOnBarTxt(state) => {
      match state.bar_txt_future.poll(cx) {
          Poll::Pending => return Poll::Pending,
          Poll::Ready(bar_txt) => {
              *self = ExampleStateMachine::End(EndState));
              // from body of `example`
              return Poll::Ready(state.content + &bar_txt);
          }
      }
  }
  ```

  最后，我们不允许在处于 End 状态的时候进行 poll，因为在之前就已经返回 Ready 或 Pending 了。

  ```rust
  ExampleStateMachine::End(_) => {
      panic!("poll called after Poll::Ready was returned");
  }
  ```

* 这只是给出了一种可行的设计。实际上 Future 状态机是基于 Generator 的，只是有一点实现上的不同。

* 另外还有一点需要说明的是：我们还需要确实的将 async fn 转变成一个 Future，可以这样做：

  ```rust
  fn example(min_len: usize) -> ExampleStateMachine {
      ExampleStateMachine::Start(StartState {
          min_len,
      })
  }
  ```

## Pinning

### 自引用结构

* 在 Future 状态机中，我们需要为每个状态保存接下来会用到的临时变量。但当我们跨暂停点借用的时候就会有一些麻烦：

  ```rust
  async fn pin_example() -> i32 {
      let array = [1, 2, 3];
      let element = &array[2];
      // 将 "3" 写入 foo.txt
      async_write_file("foo.txt", element.to_string()).await;
      // 返回 3
      *element
  }
  ```

  如前所述设计状态机，除了 Start, End 之外，我们也会设计一个 await 相关的 WaitingOnFooTxt 状态，那么里面应该保存哪些局部变量呢？

  ```rust
  struct WaitingOnWriteState {
      array: [1, 2, 3],
      element: 0x1001c, // address of the last array element
  }
  ```

  由于我们需要返回 `*element`，那么首先 `element` 必须被保存，由于它引用了 array，于是 array 也需要保存。注意这里 element 是一个指向同结构体中的字段 array 最后一个元素的一个指针，这样的结构体通常被我们称为**自引用结构**。

### 自引用结构的隐患

* 当这个结构在内存中的位置被移动的时候，自引用指针将变成一个悬垂指针。因为设计所限，自引用指针是作为一个全局指针，而非保存指向内容相对于结构体开头的位置。

### 解决方案

* 大概有三种解决方案：
  1. 当结构体被 move 的时候更新自引用指针。但是在 Rust 中这样做会带来大量的性能损失，因为要进行很多附加的运行期检验。
  2. 保存指向内容相对所在结构体开头的偏移量而非一个全局引用。这种方法的问题在于需要编译器检测所有的的自引用，但是这在编译期无法做到，只能放到运行时，会带来大量的开销，并使得某些优化无法进行。这也会带来大量的性能损失。
  3. 禁止自引用结构在内存中被移动。好处在于它只需要类型系统，在编译期就可以做到。缺点是限制了程序员的发挥。（当然 unsafe 自然无所不能）
* 由于 Rust 零成本抽象的原则，最终我们选取第三种解决方案。

### 固定在堆上

* 作者演示了如何在堆上分配一个自引用结构（保存一个指向自己位置的指针），并如何通过 `mem::replace` 或 `mem::swap` 来破坏其自引用性质。比如 `mem::replace(ref, value)` 是可以将引用的值取出并替换成给的值，然后将之前的值返回。

* 一切的原因在于我们可以通过 `Box<T>` 拿到 `&mut T`，而 `mem::replace` 或 `mem::swap` 能够通过 `&mut T` 能将本来在堆上的自引用结构**移动**到栈上或是其他地方，这样的话自引用结构性质自然就被破坏。

* ```rust
  use core::marker::PhantomPinned;
  
  struct SelfReferential {
      self_ptr: *const Self,
      _pin: PhantomPinned,
  }
  ```

  我们给结构体加上一个 `PhantomPinned` 字段，它是没有实现 `Unpin` trait 的，因此整个结构体也没有实现 `Unpin` trait。对于没有实现 `Unpin` 的类型，我们无法在 safe Rust 中从 `Pin<Box<T>>` 拿到 `&mut T`。创建 `Pin<Box<T>>` 需要从 `Box::new` 改成 `Box::pin`。

  当我们想要这样做的时候：

  ```rust
  let stack_value = mem::replace(&mut *heap_value, SelfReferential {
      self_ptr: 0 as *const _,
  });
  ```

  就会提示 `Pin<Box<SelfReferential>` 未实现 `DerefMut` trait，于是自然不能拿到 `&mut SelfReferential`。

  但是我们对于 `self_ptr` 的修改也一样会报出同样的错误。这个时候我们就需要通过 unsafe 的 `get_unchecked_mut` 来强行拿到引用。这个输入类型是 `Pin<&mut T>`，我们要先通过 `as_mut` 将 `Pin<Box<T>>` 转成 `Pin<&mut T>`。

  我们可以修改 `self_ptr`，这是因为它是在初始化没有办法，但是 `mem::replace` 本身是不允许的。如果一定要这样做的话，我们需要在 unsafe 中自己确认它的安全。

### 固定在栈上

* 性能更高，但栈的生命周期不明，你要清楚你在干什么。虽然有一些工具，但还是很困难。

### 固定与 Future

* 编译器自动生成的状态机基本上都是自引用结构，需要用 `Pin` 保护它的性质。

## Executor

* 如何合理利用多核资源？也一样可以搞一个线程池，每个 Task 在一个核上跑。这样其实和线程调度是一样的。说起来我其实并不了解线程池是怎样一种设定。但确实将 CPU 计算任务打包成一个 Future 这种挺蠢的吧，要不就是涉及到 Copy，要不就线程不安全。

  仔细想想，好像也可以做成抢下面一个共享的调度队列来着。（这几乎是万能的！）

## Waker

* 我们需要十分注意，调用 waker 接口唤醒的是 top-level Future 而不是叶子 Future。

## 协作式多任务

* 每个任务可以自己在适当的时侯保存状态，并且所有任务共用一个栈。
* 协作式多任务的特征：适当放权给任务本身，所以任务自身需要保证不会做出过分的行为来维护整体环境
* 每次要返回 Pending 之前，最小的状态会被保存在状态机内

## Context 构造

* 可以通过 `RawWaker` 构造一个类似 trait object 的家伙。因此 `RawWaker` 需要将两个指针拼在一起，一个是指向数据区域的指针，一个是指向虚表的指针。那么我们还需要先构造一个虚表，它可以用 `RawWakerVTable` 来构造。在构造虚表的时候我们需要提供这样几个方法的实现：

  ```rust
  pub const fn new(
      clone: unsafe fn(_: *const ()) -> RawWaker,
      wake: unsafe fn(_: *const ()),
      wake_by_ref: unsafe fn(_: *const ()),
      drop: unsafe fn(_: *const ())
  ) -> Self
  ```

  官方文档中说：`RawWaker` 可以用来创建一个 `Waker`，而 `Executor` 可以通过 `Waker` 来定义唤醒行为。

  我们要包装得到的 `RawWaker`，它可看成一个 trait Object，这是一个匿名 trait，只要支持 `clone, wake, wake_by_ref, drop` 几种方法即可。通常情况下我们已经有一个类，通过将它包装成 `RawWaker` 等价于为这个类实现了那个匿名 trait。要实现的四个方法的参数都是 `*const ()`，因为 `RawWaker` 并不知道我们要为什么类型 `T` 实现匿名 trait，所以在提供这些方法的时候，一种做法是将 `*const ()` 转成 `&mut T`，然后再调用类型 `T` 原生的函数来实现 `clone, wake, wake_by_ref, drop` 几种方法。

  需要注意的是，它只是与 trait object 机制相似，但并不完全就是一个 trait object。

  最简单情况下，`T` 这个类型甚至可以不存在。

  ```rust
  fn dummy_raw_waker() -> RawWaker {
      todo!();
  }
  
  fn dummy_raw_waker() -> RawWaker {
      fn no_op(_: *const ()) {}
      fn clone(_: *const ()) -> RawWaker {
          dummy_raw_waker()
      }
  
      let vtable = &RawWakerVTable::new(clone, no_op, no_op, no_op);
      RawWaker::new(0 as *const (), vtable)
  }
  ```

  进而，可以将 `RawWaker` 包装成一个 `Waker`，然后 `Context`。`Context` 就是我们在 `poll` 时所用到的参数。

  之前我们已经创建过一个最简单的 Future：

  ```rust
  async fn async_number() -> u32 {
      42
  }
  async fn example_task() {
      let number = async_number().await;
      println!("async number: {}", number);
  }
  ```

  我们要将它包装成一个 `Task`：

  ```rust
  pub struct Task {
      future: Pin<Box<dyn Future<Output = ()>>>,
  }
  impl Task {
      pub fn new(future: impl Future<Output = ()> + 'static) -> Task {
          Task {
              future: Box::pin(future),
          }
      }
      // 我们将 Task 放进 Executor 而不是 Future
      fn poll(&mut self, context: &mut Context) -> Poll<()> {
          self.future.as_mut().poll(context)
      }
  }
  ```

  这样我们就可以构造一个最简单的 `Executor`：

  ```rust
  // 只是一个 Task 队列而已
  pub struct SimpleExecutor {
      task_queue: VecDeque<Task>,
  }
  impl SimpleExecutor {
      pub fn new() -> SimpleExecutor {
          SimpleExecutor {
              task_queue: VecDeque::new(),
          }
      }
      pub fn spawn(&mut self, task: Task) {
          self.task_queue.push_back(task)
      }
  }
  ```

  我们通过 `run` 将控制权交给 `Executor`：

  ```rust
  impl SimpleExecutor {
      pub fn run(&mut self) {
          // 取出一个任务
          while let Some(mut task) = self.task_queue.pop_front() {
              // 构造一个完全空的 Context
              // 不过此时只有一个 Future 且直接返回 Poll::Ready
              // 从而我们不用担心会从 Context 中取出 Waker 并 wake 的情况
              let waker = dummy_waker();
              let mut context = Context::from_waker(&waker);
              match task.poll(&mut context) {
                  Poll::Ready(()) => {} // task done
                  // 这里的实现是，如果 Poll::Pending 的话放到队尾等待重新轮询
                  Poll::Pending => self.task_queue.push_back(task),
              }
          }
      }
  }
  ```

  这样我们就能够看到我们的 `example_task()` 运行结束了！


## 异步键盘输入

* 键盘中断是一种很好的异步任务，因为它兼具**不可预测**和**延迟敏感** 的特性。

* 中断处理只应该做**最少**的事情，比如只将键盘输入的字符读下来，剩下的数据结构操作则**不应该**放在中断处理中而是应该丢到某个后台任务里面去，不然可能错过重要的事情。

* 某种做法是，维护一个全局的 scanqueue，中断处理的时候将字符 push 进去，某个后台任务（也就是键盘任务）则在后台 pop scanqueue 并进行处理。

* **在中断里面尝试获取锁需要非常慎重**！若使用 Mutex 保护 scanqueue 并在中断处理的时候需要获取，极易导致**死锁**。比如当键盘任务持有锁的时候进入键盘中断。又或是在 scanqueue.push 的时候需要获取堆分配器的锁，而进入中断之前已经持有了该锁。

  如何才能在不使用锁的情况下完成 scanqueue.push 呢？答案是使用无锁的原子指令（本质上是**在 CPU 支持下**将临界区**缩小到一条指令**，恰好缩小到 CPU 的执行单位）。为了避免隐式在堆上分配内存，我们只能给 scanqueue 一个固定的容量。

### Rust 并发库 crossbeam

* 给出了 `ArrayQueue`，且支持 `no_std` ，只要有 `alloc` 就能用。

* 于是我们定义自己的 scanqueue:

  ```rust
  use conquer_once::spin::OnceCell;
  use crossbeam_queue::ArrayQueue;
  
  static SCANCODE_QUEUE: OnceCell<ArrayQueue<u8>> = OnceCell::uninit();
  ```

  这里用到了一个叫做 `conquer_once` 的库，和 `lazy_static!` 在功能上一样，只是它确保初始化不会在中断处理里面进行（如何做到？），这样就可进一步确保中断处理里面没有堆内存分配（`ArrayQueue` 会用到）。不是很懂，目前我们应该还是选用 `lazy_static!`。

### 队列入口

* 在键盘中断中向 scanqueue push 字符：

  ```rust
/// Called by the keyboard interrupt handler
  ///
  /// Must not block or allocate.
  pub(crate) fn add_scancode(scancode: u8) {
      if let Ok(queue) = SCANCODE_QUEUE.try_get() {
          if let Err(_) = queue.push(scancode) {
              println!("WARNING: scancode queue full; dropping keyboard input");
          }
      } else {
          println!("WARNING: scancode queue uninitialized");
      }
  }
  ```
  
  我们通过 `try_get` 来确保不会在中断处理中 alloc。注意 `ArrayQueue` 自己完成了所有的同步，我们不必再通过 `Mutex` 等 wrapper 进行保护。

### 队列出口

* 在接收端，我们建立一个 `ScancodeStream` 类型来对应键盘任务：
  
  ```rust
  pub struct ScancodeStream {
      _private: (),
  }
  
  impl ScancodeStream {
      pub fn new() -> Self {
          SCANCODE_QUEUE.try_init_once(|| ArrayQueue::new(100))
              .expect("ScancodeStream::new should only be called once");
          ScancodeStream { _private: () }
      }
  }
  ```
  
  在 `ScancodeStream::new` 中我们进行 scanqueue 的初始化。这里的黑科技在于 `_private` 字段，它能够**禁止**在模块外构造该结构体。
  
* 我们不想为 `ScancodeStream` 实现 `Future` trait，因为它并不是那种一次性买卖，收到字符后直接返回 Ready；反之这个过程需要持续进行下去。所以我们从 futures 库中找到 `Stream` trait 如下：

  ```rust
  pub trait Stream {
      type Item;
  
      fn poll_next(self: Pin<&mut Self>, cx: &mut Context)
          -> Poll<Option<Self::Item>>;
  }
  ```

  可以看到关联类型变成了一个 `Item`，状态机的推动手段从 `poll` 函数变成了 `poll_next` 函数，且返回值从 `Poll<Item>` 变成 `Poll<Option<Item>>`。直到它返回 `Ready(None)` 为止，`Exectuor` 都会不断尝试去 `poll_next` 它。大概是在 futures 库里面为它实现了 `Future` trait 来加入到 async 生态里面吧。

  首先需要引入相应的依赖：

  ```toml
  # 之所以是 futures-util 而不是 futures 是为了减少编译时间
  [dependencies.futures-util]
  version = "0.3.4"
  default-features = false
  features = ["alloc"]
  ```

  于是我们为 `ScancodeStream` 实现 `Stream` trait 如下：

  ```rust
  impl Stream for ScancodeStream {
      type Item = u8;
  
      fn poll_next(self: Pin<&mut Self>, cx: &mut Context) -> Poll<Option<u8>> {
          let queue = SCANCODE_QUEUE.try_get().expect("not initialized");
          match queue.pop() {
              Ok(scancode) => Poll::Ready(Some(scancode)),
              Err(crossbeam_queue::PopError) => Poll::Pending,
          }
      }
  }
  ```

  注意我们的 `try_get` 不会失败，因为在 `Self::new` 的时候已经初始化好了。实现也比较简单，看当前 scanqueue 里面有没有字符即可。

### 唤醒

* 就像 `Future::poll` 一样，在 `Stream::poll_next` 返回 `Poll::Pending` 的时候，我们需要注册一个回调函数，使得在新的字符到来的时候，`Executor` 能够重新关注 top-level Stream，并重新尝试 `poll_next` 它。

  因此，每个任务必须能够从传进来的 `&mut Context` 中解压出 `Waker` 并将它存在某个地方。当任务准备好的时候，被保存下来的 `Waker` 会调用 `wake` 方法，...

* 我们首先得找一个地方保存 `Waker`，但是又不能直接保存在 `ScancodeStream` 中，因为在中断处理的 `add_scancode` 阶段我们需要访问这个 `Waker` 来唤醒对应的 `Stream`。（既然如此为啥不能直接保存在 `ScancodeStream` 中？）答案同样是利用 futures 提供的工具类 `AtomicWaker`，它和 `ArrayQueue` 一样基于原子指令实现，自然支持同步互斥。

  我们定义静态的 `AtomicWaker`：

  ```rust
  use futures_util::task::AtomicWaker;
  
  static WAKER: AtomicWaker = AtomicWaker::new();
  ```

  于是，在 `poll_next` 即将返回 `Poll::Pending` 的时候，我们将从 `Context` 中得到的 `Waker` 保存在 `WAKER` 里面；并在 `add_scancode` 的时候调用 `WAKER.wake` 唤醒该异步任务。

### Waker 的保存

* 修改 `poll_next` 的实现：

  ```rust
  impl Stream for ScancodeStream {
      type Item = u8;
  
      fn poll_next(self: Pin<&mut Self>, cx: &mut Context) -> Poll<Option<u8>> {
          let queue = SCANCODE_QUEUE
              .try_get()
              .expect("scancode queue not initialized");
  
          // fast path
          // 出于性能考虑，直接返回无需考虑 waker
          if let Ok(scancode) = queue.pop() {
              return Poll::Ready(Some(scancode));
          }
  
          // 先把 Waker register 到 AtomicWaker 上
          WAKER.register(&cx.waker());
          // 再从 scanqueue 里面尝试一下
          match queue.pop() {
              Ok(scancode) => {
                  // 如果这时就有字符了，把 register cancel 掉
                  WAKER.take();
                  // 还是返回 Ready
                  Poll::Ready(Some(scancode))
              }
              Err(crossbeam_queue::PopError) => Poll::Pending,
          }
      }
  }
  ```

  奇妙的同步互斥问题：假设第一次 check 队列里面没有字符，register 之后队列里面就有了该如何处理？`Executor` 需要注意一种特殊情况：即 WAKER.register 之后，重新尝试 pop 之前进入键盘中断，尝试调用 Waker.wakeup，但此时 `poll_next` 其实还在继续运行，该如何处理呢？（其实为啥要给自己找麻烦呢，只 pop 一次不香嘛？）

### Waker 的唤醒

* 我们需要在 `add_scancode` 内调用被保存起来的 `Waker` 的 `wake` 方法：

  ```rust
  pub(crate) fn add_scancode(scancode: u8) {
      if let Ok(queue) = SCANCODE_QUEUE.try_get() {
          if let Err(_) = queue.push(scancode) {
              println!("WARNING: scancode queue full; dropping keyboard input");
          } else {
              WAKER.wake(); // new
          }
      } else {
          println!("WARNING: scancode queue uninitialized");
      }
  }
  ```

  注意我们需要将字符 push 到 scanqueue 之后再 `Waker.wake`。（这个应该取决于 waker 里面是怎么实现的）哦，但多线程情况下倒的确如此。

### 键盘任务

* 我们可以用实现了 `Stream` trait 的 `ScancodeStream` 来创建一个 `Future`：

  ```rust
  pub async fn print_keypresses() {
      let mut scancodes = ScancodeStream::new();
      let mut keyboard = Keyboard::new(layouts::Us104Key, ScancodeSet1,
          HandleControl::Ignore);
  
      while let Some(scancode) = scancodes.next().await {
          if let Ok(Some(key_event)) = keyboard.add_byte(scancode) {
              if let Some(key) = keyboard.process_keyevent(key_event) {
                  match key {
                      DecodedKey::Unicode(character) => print!("{}", character),
                      DecodedKey::RawKey(key) => print!("{:?}", key),
                  }
              }
          }
      }
  }
  ```

  `next` 方法来自于 futures 提供的另一个工具类 `StreamExt`。

  这就是一个典型的一直卡在循环里面的 Future，大概可以类比异步服务器的主循环？按照 await 点进行划分，这个大 Future 应该有两个状态：肯定有一个是等在 await 上面，poll 的时候它会尝试 poll 一下它所等待 Future，如果是 Ready 的话它就会进到下一个初始状态，否则还是继续停在这个状态；初始状态就是准备往 await 状态进行转移。这两个状态（也可能有更多状态）形成了一个环，而没有所谓的终态。

* 现在我们可以将 `print_keypresses` 加入我们的 `Executor` 并开始执行了。

  注意，之前没有注意到的一点是，对于 `async fn` 的**调用**才是一个 `dyn Future`，否则可能只是一个 `Fn`？

### 支持 Waker 的 Executor

* 之前的 Executor 并不支持 wakeup，甚至传进去的 Waker 都是空的。之所以能正常跑是因为之前的 Executor 在不断轮询 poll 我们的 Future，而键盘中断的确能往 scanqueue 里面 push 字符，于是总有一次 poll 能从 scanqueue 里面读到字符并返回 Ready，大循环也能进入下一个 cycle。 但这并不符合异步的初衷。

* 某个 `Waker.wake` 需要能够唤醒 `Executor` 内一个特定的 `Future`，就需要 `Executor` 能够区分不同的 `Future`，或者说 Task。

* 我们给每个 `Task` 一个 TaskID：

  ```rust
  #[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
  struct TaskId(u64);
  
  use core::sync::atomic::{AtomicU64, Ordering};
  
  impl TaskId {
      fn new() -> Self {
          // 突然觉得无锁天下第一！
          static NEXT_ID: AtomicU64 = AtomicU64::new(0);
          TaskId(NEXT_ID.fetch_add(1, Ordering::Relaxed))
      }
  }
  ```

* 于是现在的 `Executor` 可以变得更为复杂：

  ```rust
  pub struct Executor {
      // 根据 TaskID 查 Task
      tasks: BTreeMap<TaskId, Task>,
      // 维护一个无锁队列
      task_queue: Arc<ArrayQueue<TaskId>>,
      // 根据 TaskID 查 Waker
      waker_cache: BTreeMap<TaskId, Waker>,
  }
  ```

  这里 `TaskId` 的无锁队列需要多所有权是因为 `Executor` 和  `Waker` 都需要访问它。该队列其实就是一个**就绪队列**。交互流程是：`Waker` 将 要唤醒的 Task 的 TaskId push 到队列里面，然后 `Executor` 从队列中取出 TaskId，并根据它在 `tasks` 中查到对应的 Task，最后运行这个 Task。注意这个无锁队列也需要是固定大小的，不然在键盘中断中可能会触发 alloc。

  我们还需要一个 waker_cache 将每个 Task 专属的 Waker 保存下来。这样做有两个原因：首先是同一个 Task 的多次 wakeup 可以复用该 Waker 而不用每次都新建一个；其次是保证引用计数分配的 Waker 不至于在中断处理中触发 dealloc。

* 新建 Task

  ```rust
  impl Executor {
      pub fn spawn(&mut self, task: Task) {
          let task_id = task.id;
          // 加入 Task Map 和就绪队列
          if self.tasks.insert(task.id, task).is_some() {
              panic!("task with same ID already in tasks");
          }
          self.task_queue.push(task_id).expect("queue full");
      }
  }
  ```

* 我们通过一个私有方法 `run_ready_tasks` 来执行任务：

  ```rust
  impl Executor {
      fn run_ready_tasks(&mut self) {
          // destructure `self` to avoid borrow checker errors
          let Self {
              tasks,
              task_queue,
              waker_cache,
          } = self;
  
          while let Ok(task_id) = task_queue.pop() {
              let task = match tasks.get_mut(&task_id) {
                  Some(task) => task,
                  None => continue, // task no longer exists
              };
              let waker = waker_cache
                  .entry(task_id)
              	// 每个 Task 只会新建一次 TaskWaker
                  .or_insert_with(|| TaskWaker::new(task_id, task_queue.clone()));
              let mut context = Context::from_waker(waker);
              match task.poll(&mut context) {
                  Poll::Ready(()) => {
                      // task done -> remove it and its cached waker
                      tasks.remove(&task_id);
                      waker_cache.remove(&task_id);
                  }
                  // Pending 之后，由于已经从队列中移除，那么想要再次被 poll 
                  // 就只能靠通过 Waker.wake 将 TaskId 加入 task_queue 了
                  Poll::Pending => {}
              }
          }
      }
  }
  ```

* 设计 Waker

  ```rust
struct TaskWaker {
      task_id: TaskId,
      task_queue: Arc<ArrayQueue<TaskId>>,
  }
  impl TaskWaker {
      // 简单把 taskid push 在原子 TaskId 队列里面即可
      fn wake_task(&self) {
          self.task_queue.push(self.task_id).expect("task_queue full");
      }
  }
  ```
  
  构造 Context
  
  可以利用一个超级简单的 Wake trait
  
  ```rust
  use alloc::task::Wake;
  
  impl Wake for TaskWaker {
      // 只要实现如下两个函数即可，注意参数分别为 Arc<Self> 和 &Arc<Self>
      fn wake(self: Arc<Self>) {
          self.wake_task();
      }
  
      fn wake_by_ref(self: &Arc<Self>) {
          self.wake_task();
      }
  }
  ```
  
  这样构造 Context 就非常简单了
  
  ```rust
  impl TaskWaker {
      fn new(task_id: TaskId, task_queue: Arc<ArrayQueue<TaskId>>) -> Waker {
          Waker::from(Arc::new(TaskWaker {
              task_id,
              task_queue,
          }))
      }
  }
  ```
  
* 运行起来与主函数
  
  把 `run_ready_tasks` 包装一下：
  
  ```rust
  impl Executor {
      pub fn run(&mut self) -> ! {
          // 为了鲁棒性如果队列里面没任务了，就重新进来一次
          loop {
              self.run_ready_tasks();
          }
      }
  }
  ```
  
  主函数：spawn 两个 task
  
  ```rust
  fn kernel_main(boot_info: &'static BootInfo) -> ! {
      // […] initialization routines, including init_heap, test_main
  
      let mut executor = Executor::new(); // new
      executor.spawn(Task::new(example_task()));
      executor.spawn(Task::new(keyboard::print_keypresses()));
      executor.run();
  }
  ```
  
  
  
  
  
  

