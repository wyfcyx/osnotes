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

  1. 



