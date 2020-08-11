[200 行代码讲透 Rust Futures](https://stevenbai.top/rust/futures_explained_in_200_lines_of_rust/)

# 0. 引言

* 作者提到了 Rust 异步生态中的其他库，如 `mio, tokio, async std, Futures, libc, crossbeam`。

# 1. 背景

首先整理了一下各种常见的并发编程模式。

## 系统级线程

* 缺点：栈很大，高并发将很快耗尽内存（相比协程的确如此，由于多个线程不能共享同一个栈，造成了总和与单个的问题）；此外，系统调用的存在提高了响应延迟，且某些 OS 并不支持系统级线程。
* 现在（尤其在内核中）多任务处理无处不在。一般情况下，在多任务处理中我们需要使用线程。然而，在 webserver 中，若将每个小任务都交给一个不同的线程来处理，将造成大量的内存浪费。在负载可变的场景下问题将愈发凸显。
* 这也就是很多异步 web 库存在的原因。但是它们并不完善，还没有到达能够完全取代线程方案的地步。大多数的负载其实利用系统级线程就可以了。我只是想说——使用异步之前要三思而后行。（然而它很有趣！）

## Green Thread

* 绿色线程是多任务的另一种解决方案。
* 具体的[代码](https://cfsamson.gitbook.io/green-threads-explained-in-200-lines-of-rust/)（事实上，作者撰写了另一份有关的教程）不细看了，但我们知道它完全在用户态完成调度以及上下文切换，这样就避免了特权级切换带来的开销
* 但是肯定也存在问题：比如编程比较复杂、不能充分利用多核、跟中断打交道可能比较费力
* 最本质的问题在于：多个执行流之间仍然不共享栈，也即“总和与单个”的问题仍然没有解决

> 作者解释了为何 Rust 中最终移除了 Green Thread，其中它会导致非零成本抽象、以及栈的相关问题很难处理可能是重要原因。

## 异步： Callback style

* Callback 后面的整体思想：保存一个指向**一组指令**的一个指针，该组指令将在需要的时候被运行

* 相比 Javascript 的 Callback 地狱，Rust 的闭包实现要好上许多

* 感性理解一下基于 callback 的异步编程模式，可能大概是 

  `<阻塞调用>.callback{<返回后要做的事情>}`

  `<返回后要做的事情>` 中可能还存在 callback 的嵌套

  但是这样的感性理解并不够！

* 一位著名程序员说过：学习一门编程语言的最好办法就是**阅读源代码**，所以我来读源代码了！

* 这是 callback 代码的主函数

  ```rust
  fn program_main() {
      println!("So we start the program here!");
      set_timeout(200, || {
          println!("We create tasks with a callback that runs once the task finished!");
      });
      set_timeout(100, || {
          println!("We can even chain sub-tasks...");
          set_timeout(50, || {
              println!("...like this!");
          })
      });
      println!("While our tasks are executing we can do other stuff instead of waiting.");
  }
  ```

  其中的内容仅仅是设置阻塞一段时间之后运行闭包里面的代码。

  > 我们没有必要害怕闭包，我们知道它仅仅只是基于底层的内存管理机制以及类型系统在上层提供的函数式语法糖。实际上也就是 `FnOnce, FnMut, Fn` 三个 trait。
  >
  > 以我目前的理解，Rust 中的闭包其实就是一个附带了所有权转移机制的 C/C++ 中的函数指针，其存在的最主要目的当然是为了简化编程。当然，哪些变量会以何种形式被捕获到闭包中，则是需要仔细参考文档。
  >
  > 在 Rust 中，若是将一切都一五一十写在代码中，那也就不存在任何障碍了。但是为了 Rust 编程的简洁性，有时候势必要进行各种显式的类型转换、隐式的类型转化（似乎只在 `defer` 中存在）以及很多假装是隐式但实际上在代码某处明确给出了类型的显式类型转换。这些内容，都出现在 Rust 的类型系统中。在写 tutorial 的时候要十分注意。
  >
  > 其实，目前我觉得架构、编程语言以及上层的操作系统中的某些概念十分相似。
  
  随后，我们来看支持了 `set_timeout` 的关键结构体 `Runtime`：
  
  ```rust
  use std::sync::mpsc::{channel, Receiver, Sender};
  struct Runtime {
      callbacks: RefCell<HashMap<usize, Box<dyn FnOnce() -> ()>>>,
      next_id: RefCell<usize>,
      evt_sender: Sender<usize>,
      evt_reciever: Receiver<usize>,
  }
  ```
  
  其中 `callbacks` 保存着一个从事件 ID 到任务函数闭包的 HashMap，`next_id` 表示下一个事件的 ID，`evt_sender, evt_reciever` 则封装 `std::sync::mpsc::{Receiver, Sender}`，然而 `mpsc` 又是什么呢？实际上 `mpsc` 是一个多生产者、单消费者的基于 FIFO 的通信原语，从 `Sender` 传递到 `Receiver`。因此在这里用来传递事件，至于是什么事件还需要看后续的代码。
  
  > 显而易见，`Sender` 可以通过 `send()` 来发数据，`Receiver` 可以通过 `recv()` 来收数据。`Sender` 可以通过 `clone()` 来得到另一个可以向相同的 `Receiver` 传递消息的 `Sender`。
  >
  > `std::sync::mpsc` 可以通过 `channel()` 得到一对用一个含有无穷大缓冲的通道连接的 `(Sender, Receiver)`，无穷大缓冲意味着 `send()` 不会被阻塞，因而是**异步**的；而 `sync_channel()` 则会返回一对用一个含有有限大缓冲的通道连接的 `(SyncSender, Receiver)`，缓冲的容量在 `sync_channel` 的参数中指定。当缓冲已满时，`send()` 会被阻塞。
  
  接下来看 `Runtime` 实现的功能：
  
  ```rust
  impl Runtime {
      fn new() -> Self {
          // 创建一个异步 channel
          // 这波啊，这波是用异步实现异步
          let (evt_sender, evt_reciever) = channel();
          Runtime {
              // 一个空的映射
              callbacks: RefCell::new(HashMap::new()),
              // 初始设置下一个事件 ID 为 1
              next_id: RefCell::new(1),
              // 一对异步 Sender-Receiver
              evt_sender,
              evt_reciever,
          }
      }
  	// 运行一个任务，其中 program 是任务对应的闭包
      fn run(&self, program: fn()) {
          // 首先通过若干 set_timeout 设置 HashMap，创建对应的线程
          program();
          // 在任务执行完毕之后，从 mpsc 的接收端读取接收到的事件 ID
          for evt_id in &self.evt_reciever {
              // 根据事件 ID 在 HashMap 中查到对应 callback 闭包
              // 同时，将该事件 ID 在 HashMap 中移除
              let cb = self.callbacks.borrow_mut().remove(&evt_id).unwrap();
              // 调用 callback 函数
              cb();
              // 若此时 HashMap 为空，也即不存在任何 callback，退出循环
              if self.callbacks.borrow().is_empty() {
                  break;
              }
          }
      }
  }
  ```
  
  借此，我们来看看 `set_timeout` 是如何利用 `Runtime` 来实现的：
  
  ```rust
  // 这个 thread_local! 基于 std，裸机上不能用
  thread_local! {
      static RT: Runtime = Runtime::new();
  }
  
  // 参数很简单，也就是 timeout 的时长，以及 timeout 结束后需要被自动调用的 callback 闭包
  fn set_timeout(ms: u64, cb: impl FnOnce() + 'static) {
      RT.with(|rt| {
          // 在 RT 中分配一个事件 ID
          let id = *rt.next_id.borrow();
          *rt.next_id.borrow_mut() += 1;
          // 在 RT 的 HashMap 中插入 (id, cb) 的键值对
          rt.callbacks.borrow_mut().insert(id, Box::new(cb));
          // mpsc-async 的标准用法，clone 出可以发往同一个 Receiver 的另一个 Sender
          let evt_sender = rt.evt_sender.clone();
          // 开一个线程？？？
          // 在那个线程中 sleep 一段时间，并通过 evt_sender 给接收端发送 callback 的 ID
          thread::spawn(move || {
              thread::sleep(std::time::Duration::from_millis(ms));
              evt_sender.send(id).unwrap();
          });
      });
  }
  ```
  
  而 `main` 里面要做的这样的事情：
  
  ```rust
  fn main() {
      RT.with(|rt| rt.run(program_main));
  }
  ```
  
  事实上，在 `run` 前半部分的 `program()` 中，所有的 `set_timeout()` 都立即返回，它们要做的事情仅仅是设置底层的 `Runtime` 中的 HashMap，并新开一个线程休眠一段时间后向 `Receiver` 后发送对应的 callback ID。而在 `run` 的后半段，主线程在轮询 `Receiver`，一旦收到了某个 callback ID，证明在另一个线程上其 timeout 已到，那么就该调用 callback 函数了。
  
  那么这种做法支持 `program_main` 中用到的 `set_timeout` 嵌套吗？显然是支持的。它会在轮询到外层的 callback 之后，发现里面还有 callback，就会重新设置 HashMap 、创建新线程并等待接下来的轮询。
  
  总结一下：这份 callback 代码是基于 thread+mpsc 实现的一种模拟。而且不知道 `program_main` 的编写风格是不是正宗的 callback style，感觉有点像 VHDL，就是纯并行代码。

## 从回调到承诺

* 来自 Javascript 的 `promises` 和 Rust 中的 `Future` 是类似的概念，可以用来解决 callback 的复杂性

* 例如，将 callback 风格的 JS 代码

  ```javascript
  setTimer(200, () => {
    setTimer(100, () => {
      setTimer(50, () => {
        console.log("I'm the last one");
      });
    });
  });
  ```

  用 promises 风格进行改写：

  ```js
  function timer(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms))
  }
  
  timer(200)
  .then(() => return timer(100))
  .then(() => return timer(50))
  .then(() => console.log("I'm the last one));
  ```

  返回的 `Promise` 是一个状态机，它可以处于 `pending, fulfulled, rejected` 三种状态之一。事实上，调用 `timer(200)` 会返回一个状态处于 `pending` 的 `Promise` 状态机。
  
  事实上，JS 还提供一种更为接近阻塞式调用的异步 Promise 语法:
  
  ```js
  async function run() {
      await timer(200);
      await timer(100);
      await timer(50);
      console.log("I'm the last one");
  }
  ```
  
  除了 `async` 和 `await` 关键字之外，看起来和阻塞调用一模一样。然而每次 `await` 之后，当前的协程将会**立即**交出 CPU 使用权，而不是在原地持续等待直到当前的时间片耗尽。直到当前在等待结果的那个任务等待状态从 `pending` 变成 `fulfulled` 或 `rejected`，则它所在的协程拥有获得 CPU 使用权的资格，调度器会在合适的时机将 CPU 交给它使用。
  
  这种写法非常漂亮，但本质上和基于 `Promise` 的那段代码应该是一回事。从写法风格上看，基于 Promise 的代码与 Rust Futures 0.1 较为接近；`async/await` 版本则与如今的 Rust Futures 0.3 一致（它里面也含有 `async/await` 关键字）。然而，需要指出的是，JS 中的 Promise 与 Rust 中的 Future 的不同在于：Promise 是立即执行（early evaluated）的，一旦被创建，它就开始执行一个任务；反之，Future 是延迟执行（lazy evaluated）的，它需要通过 `poll` 才能开始执行。
  
  > 关于异步协程的一条断言如是说到：“协程能够停下来的地方是受限的。”这可以这样理解：对于一个线程，它自然可以在任意一条指令执行结束之后停下来，并将 CPU 使用权交给其他线程；而对于异步协程，它只能停在异步状态机中的某个状态，而一个状态往往可以被定位到某次 `await`——只有当它这样停下来的时候，编译器才能发挥好它的作用在栈上的一个大数据结构中保存接下来继续执行所需的信息。	
  >
  > 但是，当一个协程使用 CPU 进行计算的时候，它也有可能因时间片耗尽或者出现了优先级更高的协程而被迫交出 CPU 使用权，此时上下文信息显然也需要在栈上进行保存，而且这部分内容与 `await` 的时候保存的那个大数据结构完全是两回事。
  >
  > 这是目前我所能够想象到的协程与栈的交互方式。暂时停下来继续看教程。

# 2. Futures in Rust

* 之前提到过，Rust 中的 Future 与 JS 中的 Promise 比较相像，代表一些将在未来完成的操作。
* Rust 中的 Future 基于轮询，每个异步任务分成三个阶段：
  1. 轮询阶段（poll phase）。一个 Future 被轮询后，会开始执行直到被阻塞。通常由执行器 Executor 负责对 Future 进行轮询；
  2. 等待阶段。事件源 Reactor 注册等待一个事件发生，并确保当该事件准备好后唤醒相应的 Future。
  3. 唤醒阶段。事件发生，对应的 Future 被唤醒，执行器 Executor 调度该 Future 再一次轮询它，此时返回的结果表明继续执行的条件已满足，该异步任务会继续执行直到再一次被阻塞，回到 1 。如此不断循环直到这个异步任务全部完成。
* 我们需要将所有的 Futures 分成两类：叶子 Future 和非叶 Future。

## 叶子 Future

* 叶子 Future 在运行时被创建，并与某种 I/O 资源一一对应。比如：

  ```rust
  let mut stream = tokio::net::TcpStream::connect("127.0.0.1:3000");
  ```

  即可得到一个异步访问的 socket。

* 异步访问意味着相关的 I/O 操作（如 `read`）均立即返回一个 `Future`。

* 那么叶子 Future 和非叶 Future 有什么关系和区别呢？

## 非叶 Future

* 非叶 Future 指我们通过 `async` 关键字创建的 Future。

* 大部分异步任务以一种“可暂停的计算”的形式由非叶 Future 来描述。一般来说，它由 `await` 若干个叶子 Future 形成。如下面的代码所示：

  ```rust
  let non_leaf = async {
      let mut stream = TcpStream::connect("127.0.0.1:3000").await.unwrap();
      // yield here
      println!("connected");
      let result = stream.write(b"Hello world!\n").await;
      // yield here
      println!("message sent!");
      ...
  }
  ```

* 相比叶子 Future，非叶 Future 并非与某种 I/O 资源一一对应，而更像是多种不同 I/O 资源在 CPU 控制流的帮助下拼接在一起。当我们在 Executor 中启动对它的轮询之后，它就会开始执行，直到因等待某种 I/O 资源被阻塞、或者是占用 CPU 足够长时间之时就会交出 CPU 使用权给调度器；相关 I/O 资源可用后，它就会被唤醒，从而有资格继续占用 CPU 向下执行。

* 包含着调度器的 Executor 属于运行时范畴。那么什么是运行时呢？

## 运行时（Runtimes）

* 包括 C#, JS, Java, Go 在内的许多语言都自带一个处理并发的运行时，而 Rust 原生并没有这样的运行时，因此需要在相关的库中寻找。

* 异步的复杂性有相当一部分源自于底层运行时的复杂性，学会正确使用一个运行时就需要付出很大努力，更别提自己写一个运行时了。幸运的是，不同的运行时之间是存在相似之处的，因此只要搞懂最简单的运行时，剩下的事情就要简单一些。

* 由于 Rust 的异步运行时是在依赖库中提供的，这也赋予了 Rust 异步的灵活性，因为底层的运行时是可以自己选取甚至自己编写的。其他语言就只能使用语言自带的运行时。

* Rust 中的异步运行时可以分成两个部分：

  1. 事件源 Reactor;
  2. 执行器 Executor。

  后者负责通知一个 Future 它的等待条件达成，可以继续向下执行；后者则负责对多个 Future（也就是多个异步任务）进行执行，并在此期间负责它们的调度、管理。这两部分的功能完全独立，在中间层通过 `Waker` 进行协作。

* 目前，最受欢迎的两个 Rust 异步运行时分别是 [tokio](https://github.com/tokio-rs/tokio) 和 [async-std](https://github.com/async-rs/async-std)。

## Rust 标准库支持

* 真正要在 Rust 上写异步程序，不仅需要拓展库的运行时支持，还需要 Rust 编译器自身提供某些支持：
  1. `Future` trait 由 Rust 编译器提供；
  2. `async/await` 关键字由 Rust 编译器提供；
  3. `Waker` trait 作为 `Executor` 和 `Reactor` 协作的桥梁，也用来实际唤醒一个 `Future`，也由编译器提供。

## I/O 密集型 v.s CPU 密集型

* 来看下面一段代码：

  ```rust
  let non_leaf = async {
      // I/O Intensive: async wait for connect
      let mut stream = TcpStream::connect("127.0.0.1:3000").await.unwrap();
      // yield here
      
      // I/O Intensive: async wait for writing request
      let result = stream.write(get_dataset_request).await.unwrap();
      // yield here
      
      // I/O Intensive: async wait for reading response
      let mut response = vec![];
      stream.read(&mut response).await.unwrap();
      // yield here
      
      // CPU Intensive: analyze data 
      let report = analyzer::analyze_data(response).unwrap();
      
      // I/O Intensive: async wait for writing report
      stream.write(report).await.unwrap();
      // yield here
  }
  ```

* 注意到，在相邻两个 `yield` 点之间的代码（也即 CPU 密集型操作）和 Executor 运行在相同的线程上。这会导致一个严重的问题：当 CPU 正忙于计算时，它就不能让 Executor 来处理新发生的事件，从而唤醒目前正处于阻塞状态的某些 Future。

* 幸运的是，我们有几种不太困难的方法来解决这个问题：

  1. 开一个新线程来执行 CPU 密集型操作，并用一个叶子 Future 来以异步的状态监控它的执行状态。与其他叶子 Future 一样，当新线程上的计算任务结束，该 Future 就会被唤醒；
  
  2. 为运行时实现一个上层监控模块，可以知道每个任务各运行了多长时间，并且可以将 Executor 移动到另一个线程上去，这样的话即使 CPU 密集型操作阻塞了原来的 Executor 线程也不会导致 Executor 无响应；
  
  3. 自己写一个与运行时相匹配的 Reactor，以任何你觉得合适的方式进行 CPU 密集型操作，并返回一个能够 `await` 的 `Future`。 
  
     > 没搞懂第三种方法是个啥意思...
  
* #1 是最常见的解决方案，大多数 Executor 通过例如 `spawn_blocking` 的方法提供了对 #1 的支持；但一些 Executors 也实现了 #2。#2 的问题在于：当你换用不同的运行时的时候，你需要确保它仍然与上层监控模块兼容。否则，你的 Executor 仍有可能被阻塞。

  #3 更有理论价值，一般来说，你会很开心的将任务放入大多数运行时都会提供的线程池，在那里，你可以执行 CPU 密集型操作或者运行时不支持的“阻塞”操作。

  > 由于不懂 #3 ，这里逻辑极其混乱，词不达意。

* 已有的知识可以作为理解 Future 的一个很好的起点，但我们不能就此停下，仍然有大量的细节需要被解释。

  休息一下，接下来我们将更加深入。

## 附录

* 如果你对于并发以及异步编程十分困惑，作为在这条路上的先行者，我十分理解你们的感受。因此我撰写了一些材料试图站在更高的视角总览相关的概念，这将使后续对于 Rust Futures 的学习更加轻松。

  [异步基础之：并行与并发](https://cfsamson.github.io/book-exploring-async-basics/1_concurrent_vs_parallel.html)

  [异步基础之：异步编程的历史](https://cfsamson.github.io/book-exploring-async-basics/2_async_history.html)

  [异步基础之：处理 I/O 的策略](https://cfsamson.github.io/book-exploring-async-basics/5_strategies_for_handling_io.html)

  [异步基础之：Epoll, Kqueue 以及 IOCP](https://cfsamson.github.io/book-exploring-async-basics/6_epoll_kqueue_iocp.html)

  > 这里我们暂且不翻译，等到后面有时间了再说。

* 在学习 Rust Futures 的同时理解这些概念可能会付出一些不必要的努力，因此如果你对它们心存疑问的话，可以先试试阅读上面这些材料。

* 不用担心会被落下，我就在这里一直等着你，去吧！

* 当然，如果你对于这些概念已经非常熟悉，我们可以即刻启程。

# 3. `Waker` 与 `Context`

## 章节目标

* 理解 `Waker` 结构体是如何构造的；
* 理解运行时如何知道一个叶子 Future 可以继续执行；
* 学习 Rust 泛型系统的**动态分发**与 Trait Object 的基础知识。

## `Waker` 类型

* `Waker` 使得运行时的 Executor 部分和 Reactor 部分得以松耦合，并在功能上尽可能独立。二者的协作依赖 `Waker` 类进行，而它由编译器提供。
* 由于唤醒机制由 `Waker` 负责而不是只能由 `Executor` 进行处理，运行时的编写者可以开发更加有趣的新唤醒机制。比如开一个新线程做一些工作，并在做完之后通知 Future 可以继续执行，这整个过程均与运行时完全独立。
* 若没有 `Waker`，我们便**只能**使用 Executor 来通知一个运行中的任务；而使用 `Waker` 的话，整个系统更加灵活，我们很容易将新的叶子 Future 加入到整套系统中。

> 如果你想对 `Waker` 背后的故事进行更加深入的了解的话，我推荐[这篇文章](https://boats.gitlab.io/blog/post/wakers-i/)。

## `Context` 类型

* 在写作这篇教程的时候，`Context` 类型仅仅用于包裹 `Waker`，但未来它将给 Rust 的相关 API 的发展提供额外的灵活性。举例来说，在接下来的迭代中，`Context` 将可以管理任务的独立存储，或是为调试预留部分空间。 

## 理解 `Waker`

* 当我们在实现自己的 `Future` 的时候，如何实现一个 `Waker` 当属其中最令人困惑的问题之一。创建一个 `Waker` 涉及到创建一个虚表（vtable），它能使我们通过**动态分发**的手段在一个我们自己构造的 *type erased* （译者注：不太懂这里的 *type erased* 是什么意思，也许是指编译期就确定泛型的类型并将泛型替换为具体类型，但是和上述的**动态分发**又出现了冲突）的 Trait 对象上调用方法。

  > 关于 Rust 动态分发的[参考资料](https://alschwalm.com/blog/static/2017/03/07/exploring-dynamic-dispatch-in-rust/)
  >
  > 这里面提到了 Rust trait Object 的内存布局是 (usize, usize)，是两个指针分别指向实际类型的 data 以及 trait 类型的虚表 vtable。而每个 trait 的虚表布局大概如下所示：
  >
  > pointer to `drop`
  >
  > size
  >
  > align
  >
  > pointer to other methods...

## Rust 中的胖指针

* 为了更好理解 `Waker` 是如何实现的，我们需要回顾一些基础知识。让我们从 Rust 中一些不同的指针类型的大小开始看起。

  运行下面的代码：

  ```rust
  trait SomeTrait { }
  
  fn main() {
      println!("======== The size of different pointers in Rust: ========");
      println!("&dyn Trait:-----{}", size_of::<&dyn SomeTrait>());
      println!("&[&dyn Trait]:--{}", size_of::<&[&dyn SomeTrait]>());
      println!("Box<Trait>:-----{}", size_of::<Box<SomeTrait>>());
      println!("&i32:-----------{}", size_of::<&i32>());
      println!("&[i32]:---------{}", size_of::<&[i32]>());
      println!("Box<i32>:-------{}", size_of::<Box<i32>>());
      println!("&Box<i32>:------{}", size_of::<&Box<i32>>());
      println!("[&dyn Trait;4]:-{}", size_of::<[&dyn SomeTrait; 4]>());
      println!("[i32;4]:--------{}", size_of::<[i32; 4]>());
  }
  ```

  其结果为：

  ```rust
  ======== The size of different pointers in Rust: ========
  // trait object 分为 data 和 vtable 两个指针，因此 16 字节
  &dyn Trait:-----16
  
  // slice 类型需要保存切片的开头位置以及切片的长度，因此也是 16 字节
  &[&dyn Trait]:--16
  
  // 由于 Trait 的具体类型未知，编译期需要保存在堆上的位置以及类型的大小，故 16 字节
  Box<Trait>:-----16
  
  // i32 是 4 字节，但是引用的话是一个 64 位地址，8 字节
  &i32:-----------8
  
  // 同样是 slice 类型，16 字节
  &[i32]:---------16
  
  // 由于类型固定为 i32，只需要保存在堆上的位置，故 8 字节
  Box<i32>:-------8
  
  // 由于是一个引用，8 字节
  &Box<i32>:------8
  
  // 我们知道 &dyn Trait 也即 Trait object 大小为 16 字节，因此长度为 4 的数组大小 64 字节
  [&dyn Trait;4]:-64
  
  // 4 * 4 = 16 字节
  [i32;4]:--------16
  ```

  可以看到，某些指针的大小为 8 字节，而另一些指针的大小为 16 字节，它们被称为“胖指针”（fat pointers）：它们除了携带一个 64 位地址之外还保存了更多的信息。

* 比如 `&[i32]` 的前 8 字节保存切片的开头地址，后 8 字节保存切片的长度。

* 又比如 `&dyn Trait` 是指向一个 Trait 的引用，在 Rust 中被称为 *trait object*。它对于我们理解 `Waker` 的实现原理非常关键。那么它的 16 字节是如何组成呢？答案是：前 8 字节指向 *trait object* 的 `data` 域，后 8 字节指向 *trait object* 的虚表（`vtable`） 域。

  之所以要这样设计，是因为这使我们能够在面对一个仅仅知道它实现了哪些 Traits 接口而不知道它具体类型的时候，也能够通过这样的引用在运行时通过**动态分发**机制来调用其具体的实现。这在运行的时候才能通过查 vtable 获得方法的具体地址，因而会带来一定的开销。然而，如果编译器在编译时不能知道变量的具体类型，而只知道它实现了某个 trait，那么我们也只能使用这种办法。

* 后面给出的代码验证了 *trait object* 的内存布局：

  ```rust
  // A reference to a trait object is a fat pointer: (data_ptr, vtable_ptr)
  trait Test {
      fn add(&self) -> i32;
      fn sub(&self) -> i32;
      fn mul(&self) -> i32;
  }
  
  // This will represent our home-brewed fat pointer to a trait object
  #[repr(C)]
  struct FatPointer<'a> {
      /// A reference is a pointer to an instantiated `Data` instance
      data: &'a mut Data,
      /// Since we need to pass in literal values like length and alignment it's
      /// easiest for us to convert pointers to usize-integers instead of the other way around.
      vtable: *const usize,
  }
  
  // This is the data in our trait object. It's just two numbers we want to operate on.
  struct Data {
      a: i32,
      b: i32,
  }
  
  // ====== function definitions ======
  fn add(s: &Data) -> i32 {
      s.a + s.b
  }
  fn sub(s: &Data) -> i32 {
      s.a - s.b
  }
  fn mul(s: &Data) -> i32 {
      s.a * s.b
  }
  
  fn main() {
      let mut data = Data {a: 3, b: 2};
      // vtable is like special purpose array of pointer-length types with a fixed
      // format where the three first values has a special meaning like the
      // length of the array is encoded in the array itself as the second value.
      let vtable = vec![
          0,            // pointer to `Drop` (which we're not implementing here)
          6,            // length of vtable
          8,            // alignment
  
          // we need to make sure we add these in the same order as defined in the Trait.
          add as usize, // function pointer - try changing the order of `add`
          sub as usize, // function pointer - and `sub` to see what happens
          mul as usize, // function pointer
      ];
  
      let fat_pointer = FatPointer { data: &mut data, vtable: vtable.as_ptr()};
      let test = unsafe { std::mem::transmute::<FatPointer, &dyn Test>(fat_pointer) };
  
      // And voalá, it's now a trait object we can call methods on
      println!("Add: 3 + 2 = {}", test.add());
      println!("Sub: 3 - 2 = {}", test.sub());
      println!("Mul: 3 * 2 = {}", test.mul());
  }
  ```

  不久之后，当我们实现自己的 `Waker` 的时候事实上也要像现在所做的一样，手动设置一个虚表。当然，设置虚表的方式和现在有些许不同。但我们已经知道 *trait object* 工作的原理了，到那时可能就会稍微理解到底在干什么，而不是满头问号。

  到此为止，目前我们没有必要对于 *trait object* 与动态分发机制做到更深入的了解。

* 从[这里](https://docs.google.com/presentation/d/1q-c7UAyrUlM-eZyTo1pd8SZ0qwA_wYxmPZVOQkoDmH4/edit#slide=id.p)找到的各种胖指针的内存布局：

  ![](rust-container.png)

  有必要的时候再回过头来研究。

  以及一些与 *trait object* 相关的资料：[the book](https://doc.rust-lang.org/book/ch17-02-trait-objects.html#defining-a-trait-for-common-behavior), [all about trait objects](https://brson.github.io/rust-anthology/1/all-about-trait-objects.html)

## 附录

* 你可能很好奇为何 `Waker` 要被实现成这个样子而不是像一个普通的 Trait。
* 其原因是**灵活性**。我们实现 `Waker` 的方式让我们能够更加自由的从多种内存管理策略中选取最合适的一种。
* 比较“常规”的方式是通过引用计数 `Arc` 来监控一个 `Waker` 对象何时应当被回收。然而，这并不是唯一的方法，你也可以使用纯粹的全局函数或变量，或者其他任何你希望的手段。
* 总之，这种实现方式给运行时编写者们足够的空间以供发挥。

# 4. 生成器（Generator）与 async/await 关键字

## 章节目标

* 通过分析底层机制理解 `async/await` 语法如何发挥作用；
* 初步理解我们为何需要 `Pin`；
* 理解 Rust 异步模型为何能够高效利用内存。
* 作者提到 [RFC#2033](https://github.com/rust-lang/rfcs/blob/master/text/2033-experimental-coroutines.md) 介绍了设计 `Generator` 的动机。

## 为何学习 Generator

* 因为 Generator/yield 与 async/await 极其相似，一旦你理解了其中一个，另一个也很容易理解。此外，对于作者而言，提供一个基于 Generator 的最小化运行例程要比基于 Future 要更容易。事实上，如果基于 Future 还需要后面将提到的一系列概念，现在只是为了展示一个小例子，没有必要过早引入它们。

* async/await 工作原理和 Generator 十分接近，但是它们返回一个实现了 Future Trait 的特殊对象而不是一个 generator。在本章结尾的地方你能找到一个同时介绍 Generator 和 async/await 的非常漂亮的简介。

* 基本上，当我们在 Rust 中谈及如何处理并发的时候，有三种主要的选项：

  1. 有栈协程，通常被叫做 Green Threads；
  2. 组合器（Combinators）；
  3. 无栈协程，通常被叫做 Generators。

  我们在[之前](https://cfsamson.github.io/books-futures-explained/0_background_information.html#green-threads)已经介绍过 Green Threads，因此这里不再重复了。我们将集中介绍 Rust 目前使用无栈协程及其变体。

## 组合器 Combinators

* Rust Future 0.1 曾使用 Combinators。如果你曾在 JS 中使用过 `Promises` ，那么你就应该知道 Combinators。在 Rust 中它们看起来是这个样子：

  ```rust
  let future = Connection::connect(conn_str).and_then(|conn| {
      conn.query("some_request").map(|row| {
          SomeStruct::from(row)
      }).collect::<Vec<SomeStruct>>()
  });
  
  let rows: Result<Vec<SomeStruct>, SomeLibraryError> = block_on(future);
  ```

  这种异步实现方式主要有三个缺点：

  1. 产生的错误信息可能会非常长且难以理解；
  2. 并没有对于内存的使用进行优化；
  3. **不允许在组合器的不同步骤之间进行变量借用（borrow）**。

  事实上，第三点是其中最主要的缺点。无法在暂停点（suspension）之间进行变量借用最终会带来额外的**内存分配**与**数据拷贝**，从而使任务的执行变得极其低效。

* 它的内存使用并不理想，原因在于它是一个基于回调函数（callback）的实现，也就是说每个闭包都需要保存用来计算的所有数据。当我们将这些闭包连接（chain）在一起时，存储计算需要的数据花费的内存每经过一次连接都会增加。

  > 译者注：这里不太理解为何基于 callback 内存占用就会上升。难道 callback 和 async/await 不是一一对应的吗？

## 无栈协程/ Generator

* 这是今天我们在 Rust 中使用的异步编程模型，它有以下几个显著的优点：

  1. 将普通 Rust 代码通过 async/await 语法转换为无栈协程非常简单（甚至通过一个宏可以直接完成）；
  2. 不必进行上下文切换，以及在此过程中的 CPU 状态保存/恢复；
  3. 不必处理动态的栈分配；
  4. 内存利用非常高效；
  5. 允许我们跨暂停点进行变量借用。

  最后一点与 Rust Future 0.1 恰好相反。基于 async/await 我们可以这样做：

  ```rust
  async fn myfn() {
      let text = String::from("Hello world");
      let borrowed = &text[0..5];
      somefuture.await;
      println!("{}", borrowed);
  }
  ```

* Rust 中的异步编程模型是基于 Generator 实现的。所以为了理解 async 如何工作，我们首先需要了解 Generator 的原理。在 Rust 中，Generator 是用状态机实现的。

* 对于一系列计算构成的链，其总体的内存足迹（footprint）是每个独立计算的内存足迹的最大值。这意味着接上一个新的计算并不一定会带来更大的内存开销。这也是 Rust 中的 async 和 Future 开销如此小的原因之一。

## Generator 的工作原理

* 今天的 Nightly Rust 中我们可以在闭包里使用 `yield` 关键字，将该闭包转换为一个 Generator。当我们还不了解 `Pin` 的时候，闭包看起来可能是这样的：

  ```rust
  #![feature(generators, generator_trait)]
  use std::ops::{Generator, GeneratorState};
  
  fn main() {
      let a: i32 = 4;
      let mut gen = move || {
          println!("Hello");
          yield a * 2;
          println!("world!");
      };
      
      if let GeneratorState::Yielded(n) = gen.resume() {
          println!("Got value {}", n);
      }
      
      if let GeneratorState::Complete(()) = gen.resume() {
          ()
      };
  }
  ```

  而编译器会将代码翻译成这样：

  ```rust
  fn main() {
      let mut gen = GeneratorA::start(4);
  
      if let GeneratorState::Yielded(n) = gen.resume() {
          println!("Got value {}", n);
      }
  
      if let GeneratorState::Complete(()) = gen.resume() {
          ()
      };
  }
  
  // If you've ever wondered why the parameters are called Y and R the naming from
  // the original rfc most likely holds the answer
  enum GeneratorState<Y, R> {
      Yielded(Y),  // originally called `Yield(Y)`
      Complete(R), // originally called `Return(R)`
  }
  
  trait Generator {
      type Yield;
      type Return;
      fn resume(&mut self) -> GeneratorState<Self::Yield, Self::Return>;
  }
  
  enum GeneratorA {
      Enter(i32),
      Yield1(i32),
      Exit,
  }
  impl GeneratorA {
      fn start(a1: i32) -> Self {
          GeneratorA::Enter(a1)
      }
  }
  
  impl Generator for GeneratorA {
      type Yield = i32;
      type Return = ();
      fn resume(&mut self) -> GeneratorState<Self::Yield, Self::Return> {
          // lets us get ownership over current state
          match std::mem::replace(self, GeneratorA::Exit) {
              GeneratorA::Enter(a1) => {
  
            /*----code before yield----*/
                  println!("Hello");
                  let a = a1 * 2;
  
                  *self = GeneratorA::Yield1(a);
                  GeneratorState::Yielded(a)
              }
  
              GeneratorA::Yield1(_) => {
            /*-----code after yield-----*/
                  println!("world!");
  
                  *self = GeneratorA::Exit;
                  GeneratorState::Complete(())
              }
              GeneratorA::Exit => panic!("Can't advance an exited generator!"),
          }
      }
  }
  
  ```

  编译器自动帮我们生成了以下结构体：

  * `enum GeneratorState<Y, R>`，描述 Generator 的运行状态，由 `resume` 函数返回。若是在闭包内 yield，将返回 `Yielded(Y)`；否则是整个闭包运行结束，将返回 `Complete(R)`。

  * `trait Generator`，含有关联类型 `Yield` 和 `Return` 对应于 `GeneratorState` 中的 `Y` 和 `R`，分别表示闭包中途 yield 返回的类型以及闭包最终运行完毕返回的类型。最重要的当属 `resume` 函数，我们可以在外边调用它，来让 Generator 内包含的闭包向下运行直到遇到 yield 或者返回，此时会得到对应的 `GeneratorState`。
  
  * 接着，是编译器自动为代码中的闭包生成的特定的 Generator `GeneratorA`。可以看到，它实际上是一个状态机，含有三种状态，分别是初始状态 `Enter(i32)`、第一次 yield 状态 `Yield1(i32)`以及退出状态 `Exit`。至于 `Enter` 和 `Yield1` 内含的具体类型是编译器分析代码得到，注意到第一次 yield 的 `a * 2` 确实是一个 `i32` 类型。
  
    `GeneratorA` 实现了 `start` 函数，能够返回状态机的初始状态，也即 `GeneratorA::Enter(a1)`。
  
  接着，为 `GeneratorA` 实现 `Generator` trait，主要是 `resume` 方法的过程，则完全给出了状态机的转移。如果 `GeneratorA` 处在初始的 `Enter` 状态，`resume` 将使其运行 yield 之前的代码，yield 语句本身则会是 `GeneratorA` 进入 `Yield1` 状态并返回 `GeneratorState::Yielded`；进而，如果 `GeneratorA` 处在刚刚 yield 完的 `Yield1` 状态，调用 `resume` 方法将使它运行闭包中 yield 之后的所有代码，将 `GeneratorA` 修改为运行完毕的 `Exit` 状态，并返回 `GeneratorState::Complete`。另外，如果 `GeneratorA` 已经处在 `Exit` 状态，继续调用它的 `resume` 方法将会使程序 panic。
  
  > `yield` 关键字最早在 [RFC#1823](https://github.com/rust-lang/rfcs/pull/1823) 和 [RFC#1832](https://github.com/rust-lang/rfcs/pull/1832) 中被讨论。
  
* 现在，你已经知道 `yield` 关键字会将你的代码改写成一个状态机，你也可以初步了解 `await` 的工作原理。二者非常相像。事实上，我们上面给出的简单状态机有一些限制。设想一下，跨越 `yield` 语句进行变量借用将会发生什么事情呢？
  
* 我们知道，上面给出简单状态机并不支持这样做，比如在 `resume` 的第二个状态转移分支中借用第一个状态转移分支中声明的变量——Rust 当然严令禁止这样做。而事实上，`async/await` 语法设计上要达成的最重要的目标之一就是要支持**跨暂停点借用**。这样的借用在 Rust Future 0.1 中还不支持，所以我们自然不能止步不前。
  
* 我们先来看一下例程而不是严肃的在理论上讨论。

  > 我们将使用 Rust 目前使用的优化版的状态机。更加深入的阐述请参考 [Tyler Mandry's excellent article: How Rust optimizes async/await](https://tmandry.gitlab.io/blog/posts/optimizing-await-1/)

  ```rust
  let mut generator = move || {
      let to_borrow = String::from("Hello");
      let borrowed = &to_borrow;
      yield borrowed.len();
      println!("{} world!", borrowed);
  };
  ```

  与之前给出的 Generator 状态机相对应，我们在这里也将手写若干个不同版本的状态机，每一步我们都“手动”来实现，这会让他们看起来很不同寻常。我们也加入一些语法糖，例如为我们的 Generators 实现 `Iterator` trait 使得我们可以：

  ```rust
  while let Some(val) = generator.next() {
      println!("{}", val);
  }
  ```

  这并没有什么复杂的，但是考虑到本章的篇幅已经过长便不再赘述，但你在阅读的同时要注意。

  所以，按照和之前同样的方式，将新的闭包改写成状态机会是什么样子呢？

  ```rust
  enum GeneratorA {
      Enter,
      Yield1 {
          to_borrow: String,
          borrowed: &String, // uh, what lifetime should this have?
      },
      Exit,
  }
  
  impl Generator for GeneratorA {
      type Yield = usize;
      type Return = ();
      fn resume(&mut self) -> GeneratorState<Self::Yield, Self::Return> {
          // lets us get ownership over current state
          match std::mem::replace(self, GeneratorA::Exit) {
              GeneratorA::Enter => {
                  let to_borrow = String::from("Hello");
                  let borrowed = &to_borrow; // <--- NB!
                  let res = borrowed.len();
  
                  *self = GeneratorA::Yield1 {to_borrow, borrowed};
                  GeneratorState::Yielded(res)
              }
  
              GeneratorA::Yield1 {to_borrow, borrowed} => {
                  println!("Hello {}", borrowed);
                  *self = GeneratorA::Exit;
                  GeneratorState::Complete(())
              }
              GeneratorA::Exit => panic!("Can't advance an exited generator!"),
          }
      }
  }
  ```

  很遗憾，它无法通过编译器的检查：

  ```rust
     Compiling playground v0.0.1 (/playground)
  error[E0106]: missing lifetime specifier
    --> src/main.rs:19:19
     |
  19 |         borrowed: &String, // uh, what lifetime should this have?
     |                   ^ expected named lifetime parameter
     |
  help: consider introducing a named lifetime parameter
     |
  15 | enum GeneratorA<'a> {
  16 |     Enter,
  17 |     Yield1 {
  18 |         to_borrow: String,
  19 |         borrowed: &'a String, // uh, what lifetime should this have?
     |
  
  error: aborting due to previous error
  
  For more information about this error, try `rustc --explain E0106`.
  error: could not compile `playground`.
  
  To learn more, run the command again with --verbose.
  ```

  编译器指出我们没有给定引用 `borrowed` 的生命周期。它和 `GeneratorA` 本身，也即 `Self` 的生命周期不同，也不是 `'static`。我们会发现，局限在 Safe Rust 的小岛上，我们不可能描述清楚它的生命周期。这意味着，我们必须向编译器保证实现是安全的。

  也就是说，是时候在无边的 Unsafe Rust 汪洋中探索了。

  我们给出基于 Unsafe Rust 能够编译的代码。你将会看到我们最后用到了*自引用结构（self-referential struct）*，也就是一个保存着指向它自己的引用的结构体。

  ```rust
  enum GeneratorA {
      Enter,
      Yield1 {
          to_borrow: String,
          borrowed: *const String, // NB! This is now a raw pointer!
      },
      Exit,
  }
  
  impl GeneratorA {
      fn start() -> Self {
          GeneratorA::Enter
      }
  }
  impl Generator for GeneratorA {
      type Yield = usize;
      type Return = ();
      fn resume(&mut self) -> GeneratorState<Self::Yield, Self::Return> {
              match self {
              GeneratorA::Enter => {
                  let to_borrow = String::from("Hello");
                  let borrowed = &to_borrow;
                  let res = borrowed.len();
                  *self = GeneratorA::Yield1 {to_borrow, borrowed: std::ptr::null()};
  
                  // NB! And we set the pointer to reference the to_borrow string here
                  if let GeneratorA::Yield1 {to_borrow, borrowed} = self {
                      *borrowed = to_borrow;
                  }
  
                  GeneratorState::Yielded(res)
              }
  
              GeneratorA::Yield1 {borrowed, ..} => {
                  let borrowed: &String = unsafe {&**borrowed};
                  println!("{} world", borrowed);
                  *self = GeneratorA::Exit;
                  GeneratorState::Complete(())
              }
              GeneratorA::Exit => panic!("Can't advance an exited generator!"),
          }
      }
  }
  ```

  可以发现，`GeneratorA::Yield1` 中的 `borrowed` 字段的类型从 `&String` 变成了 `*const String`，也就是一个裸指针（raw pointer）。这是一个典型的自引用结构，因为 `borrowed` 字段是一个指向另一个字段 `to_borrow` 的指针。在初始化的时候就需要分成两个阶段：

  1. 将创建出来的 `to_borrow` 的所有权转移到 `Self` 中，这里由于在初始化的时候需要同时设置 `to_borrow` 和 `borrowed`，因此 `borrow` 先用空指针 `std::ptr::null()` 占位；
  2. 修改 `borrowed` 字段，让它指向 `Self` 中的 `String to_borrow`。这里匹配到的 `to_borrow` 应该是按照引用捕获，也就是 `&String` 类型，因此直接 `*borrowed = to_borrow` 即可。

  在下一次转移的时候就需要通过 `borrowed` 来得到字符串 `to_borrow`。捕获到的 `borrowed` 是 `& *const String` 类型，因此需要 `&**` 来得到 `to_borrow` 的引用，接下来就可以输出了。

  下面是一个在主函数中通过 `resume` 来让整个状态机跑起来的例子：

  ```rust
  pub fn main() {
      let mut gen = GeneratorA::start();
      let mut gen2 = GeneratorA::start();
      
      if let GeneratorState::Yielded(n) = gen.resume() {
          println!("Got value {}", n);
      }
      
      if let GeneratorState::Yielded(n) = gen2.resume() {
          println!("Got value {}", n);
      }
      
      if let GeneratorState::Complete(()) = gen.resume() {
          ()
      };
  }
  ```

  其结果为：

  ```rust
  Got value 5
  Got value 5
  Hello world
  ```

  这与我们想象中一致，因为 `gen` 和 `gen2` 是两个独立的状态机。`gen` 通过两次 `resume` 到达 Exit 状态，并分别返回 `Yielded(5)` 和 `Complete(())`；而 `gen2` 通过一次 `resume` 到达 `GeneratorA::Yield1` 状态，返回 `Yielded(5)`。

  但是有一个严重的问题：当我们做出 Safe Rust 允许的下述操作时：

  ```rust
  pub fn main() {
      let mut gen = GeneratorA::start();
      let mut gen2 = GeneratorA::start();
  
      if let GeneratorState::Yielded(n) = gen.resume() {
          println!("Got value {}", n);
      }
  
      std::mem::swap(&mut gen, &mut gen2); // <--- Big problem!
  
      if let GeneratorState::Yielded(n) = gen2.resume() {
          println!("Got value {}", n);
      }
  
      // This would now start gen2 since we swapped them.
      if let GeneratorState::Complete(()) = gen.resume() {
          ()
      };
  }
  ```

  我们在第一次对 `gen` 调用 `resume` 之后交换了 `gen` 和 `gen2` 的内容。我们期望它等价于连续两次对 `gen` 调用 `resume` ，而后对 `gen2` 调用 `resume` （这一次没有输出），因此，输出应当是：

  ```rust
  Got value 5
  Hello world
  ```

  然而，在 Rust 1.42 版本中，第二行会变成 ` world`；在 Rust 1.44 版本中，会发生段错误。这表明我们在仅使用 Safe Rust 的时候（译者注：明明 `GeneratorA::resume` 里面使用了 deref raw pointer 的 unsafe）出现了未定义行为以及其他的内存错误。这对于 Rust 而言的确是一个很严重的问题。

  在下一章中，我们将用一个简单的例子来清晰地说明这里发生了什么事情，同时会使用 `Pin` 来修复这一章中的 Generator。所以不必担心，接下来你就会看到哪里出了问题，以及认识到 `Pin` 是如何帮我们既方便又安全地处理自引用结构的。

  在我们描述这个问题的更多细节之前，我们先来看 Generators 和 async 关键字有什么关系，以此作为这一章的结尾。

## Generators 与 Async

* 和 Generators 一样，Rust 中的 Futures 也被实现为一个状态机。

* 你也许已经注意到 Generator 闭包与 async 块在实现上的相似之处：

  ```rust
  // Generator Closure
  let mut gen = move || {
      let to_borrow = String::from("hello");
      let borrowed = &to_borrow;
      yield borrowed.len();
      println!(" world!", borrowed);
  };
  
  // async block
  let mut fut = async {
  	let to_borrow = String::from("Hello");
      let borrowed = &to_borrow;
      SomeResource::some_task().await;
      println!(" world!", borrowed);
  };
  ```

  async 块将返回一个 Future 而不是 Generator，但 Future 和 Generator 内部的工作原理其实是一回事，只是有以下方面不同：

  1. 推进状态机的状态时我们不再调用 `Generator::resume` 而是换成 `Future::poll`；
  2. 返回值类型不再是 `GeneratorState::{Yielded, Complete}` 而是改成 `Future::{Pending, Ready}`。

  而在暂停点方面，Generator 中的 yield 和 Future 中的 await 基本是一一对应的。

  现在我们清楚它们之间的联系了。这也就是我们为什么先介绍 Generator 的工作原理并探讨实现过程中有哪些挑战，关于 Future 我们同样会面对这些问题。比如，跨暂停点进行变量借用就是一个重要的共通的问题。

## 附录：Rust 目前使用的自引用 Generator

* 感谢 [PR#45337](https://github.com/rust-lang/rust/pull/45337/files)，事实上我们现在在 Nightly Rust 中已经可以使用 `static` 关键字来实现本章提到的例子了。你可以亲自动手尝试一下！

  > 注意相关的 API 变化非常迅速。当我在写作这本教程时，Generator 的 API 又出现了新的变化：可以将 `resume` 的参数传入 Generator 闭包中。
  >
  > 相关进展可以在 [issue #4312](https://github.com/rust-lang/rust/issues/43122) 和 [RFC#033](https://github.com/rust-lang/rfcs/blob/master/text/2033-experimental-coroutines.md) 中找到。

  ```rust
  #![feature(generators, generator_trait)]
  use std::ops::{Generator, GeneratorState};
  
  
  pub fn main() {
      let gen1 = static || {
          let to_borrow = String::from("Hello");
          let borrowed = &to_borrow;
          yield borrowed.len();
          println!("{} world!", borrowed);
      };
  
      let gen2 = static || {
          let to_borrow = String::from("Hello");
          let borrowed = &to_borrow;
          yield borrowed.len();
          println!("{} world!", borrowed);
      };
  
      let mut pinned1 = Box::pin(gen1);
      let mut pinned2 = Box::pin(gen2);
  
      if let GeneratorState::Yielded(n) = pinned1.as_mut().resume(()) {
          println!("Gen1 got value {}", n);
      }
  
      if let GeneratorState::Yielded(n) = pinned2.as_mut().resume(()) {
          println!("Gen2 got value {}", n);
      };
  
      let _ = pinned1.as_mut().resume(());
      let _ = pinned2.as_mut().resume(());
  }
  
  ```

  其运行结果为：

  ```rust
  Gen1 got value 5
  Gen2 got value 5
  Hello world!
  Hello world!
  ```

  与我们的预期一致。

# 5. `Pin`

> `Pin` 在 [RFC#2349](https://github.com/rust-lang/rfcs/blob/master/text/2349-pin.md) 中被提出。

## 章节目标

* 学习如何使用 `Pin`，并了解为何它在我们自己实现 `Future` 的过程中不可或缺；
* 理解在 Rust 中如何安全使用自引用结构；
* 学习跨暂停点（await）的变量借用是怎样被实现的；
* 了解一系列跟 `Pin` 打交道的宝贵经验。

让我们直接开始吧。Pinning 属于那种在刚接触的时候很难想清楚的东西，但是一旦你建立起它的心智模型，它的一切就会变得非常容易理解。

## 定义





  



  

  

  

  

