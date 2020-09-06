# lab4

## 第三版实现

* 第三版的 lab4 实现是与原版不同之处最大的地方，所以这里再从设计与实现的角度梳理一下。

* 从功能依赖的角度来看：

  ```mermaid
  graph TD;
  Thread --> Process;
  Thread --> Context;
  Processor --> Thread;
  Processor --> Scheduler;
  Processor --> Lock;
  Interrupt --> Processor;
  Thread --> KernelStack;
  KernelStack --> Context;
  ```

* 这样看起来好像还蛮清晰的。那我们接下来自底向上梳理一下相应的接口。

* 关中断锁 Lock。

  这里无需给出代码，只需明白 Lock 是对 spin::Mutex 在外层进行的封装，保证在关闭中断下运行。

  与中断的交互可谓设计的核心部分，我们接下来再分析相关的内容。

* 进程 Process。

  ```rust
  pub struct Process {
      // 固有属性，表示用户进程还是内核进程（即内核本身）
      pub is_user: bool,
      pub inner: Mutex<ProcessInner>,
  }
  
  pub struct ProcessInner {
      pub memory_set: MemorySet,
      pub descriptors: Vec<Arc<dyn INode>>,
  }
  
  impl Process {
      // 新建一个内核进程
      // 主要是要建一套页表
      pub fn new_kernel() -> MemoryResult<Arc<Self>>;
      
      // 新建一个 ELF 进程（可能是用户、也可能是内核）
      // 也是要建一套页表，并将来源之处的数据写进去
      pub fn from_elf(file: &ElfFile, is_user: bool) -> MemoryResult<Arc<Self>>;
      
      // 为可变的部分提供内部可变性
      pub fn inner(&self) -> spin::MutexGuard<ProcessInner>;
      
      // 在进程的虚拟地址空间里面以 FRAMED 方式新映射一个虚拟地址区间
      // 大小、访问权限给定。
      pub fn alloc_page_range(
          &self,
          size: usize,
          flags: Flags,
      ) -> MemoryResult<Range<VirtualAddress>>;
  }
  ```

  Summary: Process 目前主要管理一个 MemorySet（也即进程内可用的虚拟地址空间），提供新建、修改功能。修改功能主要体现在 `alloc_page_range` 函数。

* 中断上下文 Context。

  主要是新增了一个函数，为线程构造一个初始化的上下文：

  ```rust
  pub fn new(
      stack_top: usize,
      entry_point: usize,
      arguments: Option<&[usize]>,
      is_user: bool,
  ) -> Self;
  // @stack_top 会影响 sp 寄存器
  // @entry_point 会影响 sepc 寄存器
  // @arguments 会影响 x10, x11, ... 寄存器
  // @is_user 会影响 sstatus.sum 寄存器
  // 此外，sstatus.spie 会被设置，使得线程跑起来之后打开 S Mode 中断
  ```

* 中断栈 KernelStack，实例化为 .bss 内的一小段空间。

  核心函数为：

  ```rust
  pub fn push_context(&mut self, context: Context) -> *mut Context;
  ```

  将 Context 固定在此段空间的最上方并返回其开头地址。

  那么这一小段空间的其他地方会不会被用到呢。我们为何不弄一个 `static mut Context` 呢？

* 线程 Thread，实现用到了 Process 和 Context，与资源和运行时特征分别对应。

  ```rust
  pub struct Thread {
      // 以下是一些自创建伊始就不会再改动的内容
      // 线程 ID
      pub id: ThreadID,
      // 运行栈，这个栈是在所属的进程的地址空间里映射的
      pub stack: Range<VirtualAddress>,
      // 所属进程
      pub process: Arc<Process>,
      pub inner: Mutex<ThreadInner>,
  }
  
  pub struct ThreadInner {
  	// 当在中断里面决定要交换当前线程（中断之前运行的那个线程）的 CPU 使用权的时候，
      // 会将该线程的中断上下文存在该线程的 TCB 里面，这是跟原版一个很大的不同
      pub context: Option<Context>,
      // 运行状态
      pub sleeping: bool,
      pub dead: bool,
  }
  
  impl Thread {
      // 在进程下面新建一个线程
      pub fn new(
          process: Arc<Process>,
          entry_point: usize,
          arguments: Option<&[usize]>,
      ) -> MemoryResult<Arc<Thread>>;
      // 获取内部可变的部分
      pub fn inner(&self) -> spin::MutexGuard<ThreadInner>;
      // TCB 内保存的中断上下文 --> 中断栈（通常与 __restore 组成一个 Combo）
      // 考虑到所属进程不同，还需要对于 satp 进行切换。
      pub fn prepare(&self) -> *mut Context;
      // 将线程进入中断处理之前保存的中断上下文 --> TCB 内保存的中断上下文
      pub fn park(&self, context: Context);
  }
  ```
  
  除新建和访问内部可变部分之外，线程向上提供的接口主要是 `park` 和 `prepare`，主要体现中断上下文拿入/拿出 TCB 的过程。
  
* 调度器 Scheduler 以及具体实现 SchedulerImpl。

  ```rust
  pub trait Scheduler<ThreadType: Clone + Eq>: Default {
      /// 优先级的类型
      type Priority;
      /// 向线程池中添加一个线程
      fn add_thread(&mut self, thread: ThreadType);
      /// 获取下一个时间段应当执行的线程
      fn get_next(&mut self) -> Option<ThreadType>;
      /// 移除一个线程
      fn remove_thread(&mut self, thread: &ThreadType);
      /// 设置线程的优先级
      fn set_priority(&mut self, thread: ThreadType, priority: Self::Priority);
  }
  ```

  接口基本和之前一致。`add_thread` 向线程池中加入线程，`get_next` 从线程池中选出一个线程用于接下来的运行，`remove_thread` 将一个线程从线程池中移除。

* 调度单元 Processor。

  ```rust
  #[derive(Default)]
  pub struct Processor {
      // 当前线程
      current_thread: Option<Arc<Thread>>,
      // 调度队列
      scheduler: SchedulerImpl<Arc<Thread>>,
      // 等待队列
      sleeping_threads: HashSet<Arc<Thread>>,
  }
  
  impl Processor {
      // 获取当前线程的一个引用
      pub fn current_thread(&self) -> Arc<Thread>;
  
      // 当要换一个线程运行的时候调用该函数
      // 功能：从调度队列选出一个线程，并 prepare 将中断上下文从 TCB -> 中断栈
      pub fn prepare_next_thread(&mut self) -> *mut Context;
      // 当前线程（进入 Trap 之前所执行线程）Trap 后要被更换时调用
      // 实现：调用 Thread::park，中断上下文从被保存的中断上下文 -> TCB
      pub fn park_current_thread(&mut self, context: &Context);
      
      // 将一个线程加入调度队列。
      pub fn add_thread(&mut self, thread: Arc<Thread>);
      // 唤醒一个线程。
      // 实现：从等待队列移除，加入调度队列。
      pub fn wake_thread(&mut self, thread: Arc<Thread>);
      // 当前线程由于某种原因被迫阻塞的时候调用该函数。
      // 功能：修改线程状态，并从调度队列移入等待队列。
      pub fn sleep_current_thread(&mut self);
      // 当前线程退出的时候（又是另一处与中断挂钩的地方）调用。
      // 功能：从调度队列中移除
      pub fn kill_current_thread(&mut self)：
      
  }
  ```

  由此可以将 Processor 的功能分成两个方面：

  * 封装 Thread 的 `park/prepare` 功能，同样具有中断上下文交换的功能。

    事实上两个函数也体现了线程状态的变化：

    `park_current_thread` 体现了运行 -> 就绪状态；

    `prepare_next_thread` 体现了就绪 -> 运行状态。

    二者通常组合用于交换 CPU 使用权的场景。

  * **仅**将线程在两个队列上进行转移，体现了线程状态的变化：

    `add_thread` 将线程加入调度队列，体现了初始化 -> 就绪状态；

    `wake_thread` 将线程从等待队列移动到调度队列，体现了阻塞 -> 就绪状态；

    `sleep_current_thread` 将线程从调度队列移动到等待队列，体现了运行 -> 阻塞状态；

    `kill_current_thread` 将线程从调度队列中删除，体现了运行 -> 退出状态。

  于是我们可以再绘制一张图说明这一点：

  ```mermaid
  graph LR;
  subgraph switching
  Running-- park_current_thread -->Ready;
  Ready-- prepare_next_thread -->Running;
  end
  Init-- add_thread -->Ready;
  Blocking-- wake_thread-->Ready;
  Running-- sleep_current_thread-->Blocking;
  Running-- kill_current_thread-->Exited;
  ```

* 中断处理 Interrupt。

  从中断处理的角度来看，所有函数的返回值都变成了 `*mut Context`，变成了接下来要执行的线程进入中断之前被保存的上下文，其实都是为了时钟中断中可能会发生的线程切换在服务。中断处理结束 `__restore` 的时候会从这个 `Context` 上面恢复 CPU 状态并继续执行要执行的那个线程。

  那么 `__restore` 传入的 a0 从哪里来？要么是主动调用 `__restore` 函数强行启动一个线程，此时自然要传入其 `*mut context`；要么是 `handle_interrupt` 的返回值由于调用规范存储在 a0 寄存器中。

  此外中断处理都要在中断栈上进行。包括中断上下文保存以及从 TCB 拿出中断上下文用于切换线程。可以看到在保存中断上下文之前进行了换栈，将线程执行的栈顶保存在 `sscratch` 寄存器中，而从 `sscratch` 寄存器中得到中断栈的栈顶（它应当是一个常数）。也就是在每次保存中断之前都要保证 `sscratch` 寄存器中保存着中断栈的栈顶，这里 `sscratch` 的值是第一次 `__restore` 写进去的。

## 有关串口的阻塞

* 原来用户程序里面是一个 loop，这样的话它从休眠回来跳转到 ecall 下一条指令也可以的了。毕竟又会回到 loop 开头的 ecall，这时里面就有数据，能直接返回了。

  这样做确实没有浪费 CPU 资源，达到了它的目的。

### 阻塞篇

* 下面我们来整理一下函数的调用链。

  用户态 `console.rs` 里面如 `getchar` 函数：

  ```rust
  pub fn getchar() -> u8 {
      let mut c = [0u8; 1];
      sys_read(STDIN, &mut c);
      c[0]
  }
  ```

  这里 `sys_read` 对上是阻塞的，但实现方法是轮询：

  ```rust
  pub fn sys_read(fd: usize, buffer: &mut [u8]) -> isize {
      loop {
          let ret = syscall(
              SYSCALL_READ,
              fd,
              buffer as *const [u8] as *const u8 as usize,
              buffer.len(),
          );
          if ret > 0 {
              return ret;
          }
      }
  }
  ```

  这里之所以要用循环，是因为阻塞后被唤醒之后，会回到 ecall 的下一条指令执行。这是 syscall 的实现机制导致的。因此不用 loop 的话就拿不到字符了。

  保存中断上下文 `__interrupt` 是在中断栈上进行的（上面解释了换栈的原理），保存了 x0~x31，其中 x2 也即 sp 要特殊处理。此外，还需要传入当前的栈顶位置，scause, stval 作为 `handle_interrupt` 的参数。

  接着调用 `handle_interrupt`。首先检查当前线程是否主动退出，如果退出的话直接换，这个比较特殊。还是看 syscall 这里，转发到 `syscall_handler`。

  `kernel/syscall.rs` 这里，注意到强制性将 `sepc += 4` ，这样无论什么情况下等到回到线程继续执行的时候，都是从 ecall 的下一条指令开始执行。这也就是说为何用户态的 `sys_read` 要使用轮询来实现。

  假设是输入字符，转发到内核内部的 `sys_read` 实现。这里要去当前线程所属的进程下面去查文件描述符表拿到相应的 INode 来提供 `read_at, write_at` 功能。内核进程在初始化的时候就已经把标准输入输出（fd = 0;1，表示串口输入输出），它们对 Inode 接口的实现也可以在 `fs` 文件夹内找到。

  那我们找到 `stdin.rs` 里面的 `read_at` 函数，`Stdin` 结构体里面有一个缓冲区 `buffer`，如果是空的话就会将当前的线程挂在 `Stdin` 结构体内部的条件变量里面，这是指将当前线程放入条件变量内部的队列里，然后通过 `sleep_current_thread` 将当前线程移除出调度队列。

  但是线程这个时候还在接着跑，并不像第二版那个时候直接 yield 就下台了。条件变量的处理结束后，`Stdin::read_at` 返回了一个 `Ok(0)`。该结果返回给内核的 `sys_read` 函数，它发现虽然是 Ok，但是实际返回的长度是 0，说明缓冲区里面暂时没有东西，需要被阻塞，它进而返回一个 `SyscallResult::Park`。

  该结果返回给 `syscall_handler` 函数，它发现返回值是一个 `Park`，说明需要被阻塞。但是它也会把返回值写入上下文中的 a0 寄存器。接着完成了一次典型的线程 switch：将修改过后的中断上下文（仅仅修改了 sepc 还有 x10）保存在 TCB 中，接着从调度器中找到下一个线程，将它的中断上下文从 TCB 取到中断栈中，返回它的位置。这样该返回值被 `handle_interrupt` 函数接收到并直接原样返回，经过`__restore`，新的线程就开始执行了。

### 唤醒篇

* 终于我们通过键盘输入了一个字符，这将触发串口中断，`console_getchar` 是基于 sbi 的一个非阻塞调用，由于产生了中断，RXFIFO 里必定有东西，因此能够拿到一个字符。然后调用 `Stdin::push`，将字符丢进缓冲区，并试图唤醒等待该输入的线程。
* 刚才阻塞的线程被唤醒，从等待队列回到调度队列。而当时机合适，它获得 CPU 使用权的时候，在 `__restore` 之后它会位于 ecall 的下一条指令，且 a0 寄存器会是 syscall 的返回值。当然，此时它还是 0。按照用户态 `sys_read` 的视角来看，这不过是这一次暂时没读到而已，它会再尝试一次。它不知道的是：它很幸运，下一次一定能够读到，不然它就不会被唤醒了。
* 将流程再走一次 ，`Stdin::read_at` 将能够从 buffer 里面取出一个字符并返回 Ok(>0)，随后 `sys_read` 也将会返回 `SyscallResult::Proceed` 继续执行当前的线程，进而 `syscall_handler` 返回的 `*mut Context` 也仍是不久之前在中断栈上保存的那个，只是做了一点小小的修改。它会被 `handle_interrupt` 原样返回，经过 `__restore` 回到线程执行仍是在 ecall 下一条指令，但此时 a0 已经确实有一个字符了，从而循环 break，用户态 `sys_read` 终于返回了。
* 接着，从 `sys_read` 那里拿到字符的 `getchar` 也终于返回了！这个漫长的过程终于结束了。

## 中断

* 中断（特别是时钟中断）和锁的交互相对而言是比较复杂的事情。那么在第三版里面又是如何处理的呢？
* 为何在 PROCESSOR 的 Mutex 锁外面还要包一层关闭中断临界区呢？
* 这里的考虑是可能**在内核线程中**访问 PROCESSOR。如果是这样的话，若在持有 PROCESSOR 的情况下进入中断，现在的中断与线程调度严重相关，故而极有可能产生死锁。当然，这种情况也就仅限于内核线程中访问 PROCESSOR 的情况。
* 现在中断处理里面并未尝试打开中断，因此不会在奇怪的地方进入调度。