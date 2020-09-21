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



