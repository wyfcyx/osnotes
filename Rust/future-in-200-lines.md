[200 行代码讲透 Rust Futures](https://stevenbai.top/rust/futures_explained_in_200_lines_of_rust/)

# 1. 引言

* 作者提到了 Rust 异步生态中的其他库，如 `mio, tokio, async std, Futures, libc, crossbeam`。

# 2. 背景

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
  
  

