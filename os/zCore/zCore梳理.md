启动，以RISC-V平台为例，找到`zCore/src/platform/riscv/entry.rs`，可以看到熟悉的`_start`入口点。同时还能找到链接脚本`linker64.ld`。然后有一个`select_stack`根据硬件线程编号设置启动栈，然后进入`primary_rust_main`。在这个函数中，首先清零`.bss`段，然后是一个暂时不知道什么作用的启动页表初始化，接着是在SBI IPI支持下的多核启动，最后转交控制权到`crate::primary_main`也就是`zCore/src/main.rs`中的`primary_main`函数。

在`primary_main`函数中，依次（挑重要的说）：

* 使能堆分配

* 调用`kernal_hal::primary_init_early`函数，感觉具体实现应该是在`kernal_hal/bare(libos)/boot.rs`中。

* 通过传进来的`BootOptions`（注意在裸机和libos下行为不同，分别是基于`kernel_hal::boot::cmdline()`和标准命令行参数）配置log打印

* 初始化物理页帧分配器

* 调用`kernel_hal::primary_init`函数

* 通过原子变量告知其他核启动核初始化完成，从而其他核可以调用同文件下的`secondary_main`函数（感觉这里似乎有点问题，至少在RISC-V平台上同时存在两种多核启动机制？这里我们姑且先忽略这些细节）

* 最后是根据Linux和Zircon平台的不同启动第一个进程。这里我们关注Linux平台，代码如下：

  ```rust
  let args = options.root_proc.split('?').map(Into::into).collect(); // parse "arg0?arg1?arg2"
  let envs = alloc::vec!["PATH=/usr/sbin:/usr/bin:/sbin:/bin".into()];
  let rootfs = fs::rootfs();
  let proc = zcore_loader::linux::run(args, envs, rootfs);
  utils::wait_for_exit(Some(proc))
  ```

  可以看到其中的核心是调用`zcore_loader`模块加载ELF文件的各段到内存中，并创建对应的进程控制块。具体实现在`loader/src/linux.rs`中的`run`函数。仔细观察一下，其中的`Job/Process/Thread`结构均继承自`zircon_object` crate。相对的，`linux_object` crate中提供了若干拓展如下：

  ```rust
  use linux_object::fs::{vfs::FileSystem, INodeExt};
  use linux_object::thread::{CurrentThreadExt, ThreadExt};
  use linux_object::{loader::LinuxElfLoader, process::ProcessExt};
  ```

  具体run的流程如下：

  ```rust
  // 依次创建job->proc->thread
  let job = Job::root();
  let proc = Process::create_linux(&job, rootfs.clone()).unwrap();
  let thread = Thread::create_linux(&proc).unwrap();
  // 创建 elf loader，提供 syscall入口地址/用户栈页数/以及文件系统的根索引节点
  let loader = LinuxElfLoader {
      syscall_entry: kernel_hal::context::syscall_entry as usize,
      stack_pages: USER_STACK_PAGES,
      root_inode: rootfs.root_inode(),
  };
  // 在文件系统中索引ELF文件并将数据读到内存，即data变量中
  let inode = rootfs.root_inode().lookup(&args[0]).unwrap();
  let data = inode.read_as_vec().unwrap();
  let path = args[0].clone();
  
  let pg_token = kernel_hal::vm::current_vmtoken();
  debug!("current pgt = {:#x}", pg_token);
  // 将数据拷贝到进程虚拟地址空间中，并调整内存布局，返回应用入口地址和栈指针
  let (entry, sp) = loader.load(&proc.vmar(), &data, args, envs, path).unwrap();
  //调用zircon-object/src/task/thread.start设置好要执行的thread
  thread
      .start_with_entry(entry, sp, 0, 0, thread_fn)
      .expect("failed to start main thread");
  proc
  ```

  那么这里的`thread_fn`是什么呢？

  ```rust
  fn thread_fn(thread: CurrentThread) -> Pin<Box<dyn Future<Output = ()> + Send + 'static>> {
      Box::pin(run_user(thread))
  }
  ```

  此处的`run_user`是一个`async fn`。因此其作用是将参数`thread`传进一个Future中并将这个Future固定在堆上。我自己写的`async_modules`也参考了这种思路。然后来看一下`start_with_entry`的实现，可以在`zircon_object/src/task/thread.rs`中作为`Thread`类型的成员函数找到：

  ```rust
  pub fn start_with_entry(
      self: &Arc<Self>,
      entry: usize,
      stack: usize,
      arg1: usize,
      arg2: usize,
      thread_fn: ThreadFn,
  ) -> ZxResult {
      self.with_context(|ctx| ctx.setup_uspace(entry, stack, &[arg1, arg2, 0]))?;
      self.start(thread_fn)
  }
  
  /// Access saved context of current thread, or `Err(ZxError::BAD_STATE)` if
  /// the thread is running.
  pub fn with_context<T, F>(&self, f: F) -> ZxResult<T>
  where
  F: FnOnce(&mut UserContext) -> T,
  {
      let mut inner = self.inner.lock();
      if let Some(ctx) = inner.context.as_mut() {
          Ok(f(ctx))
      } else {
          Err(ZxError::BAD_STATE)
      }
  }
  ```

  `with_context`的作用是在返回用户态之前调整对应的`UserContext`，包括PC/SP以及命令行参数。该`UserContext`被`Thread.inner`上锁保护，因此应该是每个线程都有一个`UserContext`。然后来看`start`的实现：

  ```rust
  /// Start execution on the thread.
  pub fn start(self: &Arc<Self>, thread_fn: ThreadFn) -> ZxResult {
      // 调整当前Thread的运行状态
      self.inner
          .lock()
          .change_state(ThreadState::Running, &self.base);
      // 将当前Thread封装到一个CurrentThread中
      let current = CurrentThread(self.clone());
      // 将CurrentThread传入到上面提到的run_user Future闭包中
      let future = thread_fn(current);
      // 将上述的run_user Future闭包进一步包裹在一个ThreadSwitchFuture中
      kernel_hal::thread::spawn(ThreadSwitchFuture::new(self.clone(), future));
      Ok(())
  }
  
  // 顺带一提，CurrentThread是Thread的简单封装。
  pub struct CurrentThread(Arc<Thread>);
  ```

  关于`ThreadSwitchFuture`可以和`Thread`在同样的文件下找到。
  
  ```rust
  struct ThreadSwitchFuture {
      thread: Arc<Thread>,
      future: Mutex<ThreadFuturePinned>,
  }
  
  impl Future for ThreadSwitchFuture {
      type Output = ();
      fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
          cfg_if! {
              if #[cfg(all(target_os = "none", target_arch = "aarch64"))] {
                  use kernel_hal::arch::config::USER_TABLE_FLAG;
                  kernel_hal::vm::activate_paging(self.thread.proc().vmar().table_phys() | USER_TABLE_FLAG);
              } else {
                  kernel_hal::vm::activate_paging(self.thread.proc().vmar().table_phys());
              }
          }
          self.future.lock().as_mut().poll(cx)
      }
  }
  ```
  
  在`poll`的实现方面，注意到首先需要切换到当前`Thread`所在进程的地址空间，这也就是为什么我们需要在该Future中再保存一份`Arc<Thread>`。不过目前还不太清楚`ThreadSwitchFuture`里面的`future`是否有必要上锁。
  
  简单看一下`run_user`的实现（可以在`loader/src/linux.rs`中找到）：
  
  ```rust
  /// The function of a new thread.
  ///
  /// loop:
  /// - wait for the thread to be ready
  /// - get user thread context
  /// - enter user mode
  /// - handle trap/interrupt/syscall according to the return value
  /// - return the context to the user thread
  async fn run_user(thread: CurrentThread) {
      kernel_hal::thread::set_tid(thread.id(), thread.proc().id());
      loop {
          // wait
          let mut ctx = thread.wait_for_run().await;
          if thread.state() == ThreadState::Dying {
              break;
          }
  
          // check the signal and handle
          let (signals, sigmask, handling_signal) = thread.inner().lock_linux().get_signal_info();
          if signals.mask_with(&sigmask).is_not_empty() && handling_signal.is_none() {
              let signal = signals.find_first_not_mask_signal(&sigmask).unwrap();
              thread.lock_linux().handling_signal = Some(signal as u32);
              ctx = handle_signal(&thread, ctx, signal, sigmask).await;
          }
  
          // run
          debug!(
              "go to user: tid = {} pc = {:x}",
              thread.id(),
              ctx.get_field(UserContextField::InstrPointer)
          );
          // trace!("ctx = {:#x?}", ctx);
          ctx.enter_uspace();
          debug!(
              "back from user: tid = {} pc = {:x} trap reason = {:?}",
              thread.id(),
              ctx.get_field(UserContextField::InstrPointer),
              ctx.trap_reason(),
          );
          // trace!("ctx = {:#x?}", ctx);
          // handle trap/interrupt/syscall
          if let Err(err) = handle_user_trap(&thread, ctx).await {
              thread.exit_linux(err as i32);
          }
      }
  }
  ```
  
  首先看一下`thread.wait_for_run().await`是怎么回事。
  
  ```rust
  // 顺带一提，CurrentThread是Thread的简单封装。
  pub struct CurrentThread(Arc<Thread>);
  
  // 各种 ThreadState，与 Thread 在相同文件下
  /// The thread state.
  #[derive(Debug, Clone, Copy, Eq, PartialEq)]
  pub enum ThreadState {
      /// The thread has been created but it has not started running yet.
      New = 0,
      /// The thread is running user code normally.
      Running = 1,
      /// Stopped due to `zx_task_suspend()`.
      Suspended = 2,
      /// In a syscall or handling an exception.
      Blocked = 3,
      /// The thread is in the process of being terminated, but it has not been stopped yet.
      Dying = 4,
      /// The thread has stopped running.
      Dead = 5,
      /// The thread is stopped in an exception.
      BlockedException = 0x103,
      /// The thread is stopped in `zx_nanosleep()`.
      BlockedSleeping = 0x203,
      /// The thread is stopped in `zx_futex_wait()`.
      BlockedFutex = 0x303,
      /// The thread is stopped in `zx_port_wait()`.
      BlockedPort = 0x403,
      /// The thread is stopped in `zx_channel_call()`.
      BlockedChannel = 0x503,
      /// The thread is stopped in `zx_object_wait_one()`.
      BlockedWaitOne = 0x603,
      /// The thread is stopped in `zx_object_wait_many()`.
      BlockedWaitMany = 0x703,
      /// The thread is stopped in `zx_interrupt_wait()`.
      BlockedInterrupt = 0x803,
      /// Pager.
      BlockedPager = 0x903,
  }
  
  
  // 下面是wait_for_run的实现
  impl CurrentThread {
      /// Wait until the thread is ready to run (not suspended),
      /// and then take away its context to run the thread.
      pub fn wait_for_run(&self) -> impl Future<Output = Box<UserContext>> {
          #[must_use = "wait_for_run does nothing unless polled/`await`-ed"]
          struct RunnableChecker {
              thread: Arc<Thread>,
          }
          impl Future for RunnableChecker {
              type Output = Box<UserContext>;
  
              fn poll(self: Pin<&mut Self>, cx: &mut Context) -> Poll<Self::Output> {
                  let mut inner = self.thread.inner.lock();
                  if inner.state() != ThreadState::Suspended {
                      // resume:  return the context token from thread object
                      // There is no need to call change_state here
                      // since take away the context of a non-suspended thread won't change it's state
                      Poll::Ready(inner.context.take().unwrap())
                  } else {
                      // suspend: put waker into the thread object
                      inner.waker = Some(cx.waker().clone());
                      Poll::Pending
                  }
              }
          }
          RunnableChecker {
              thread: self.0.clone(),
          }
      }
  }
  ```
  
  这里，当`Thread`的状态非`ThreadState::Suspended`的时候（该状态似乎与一个奇怪的名为`zx_task_suspend`的系统调用有关，具体参考`zircon_syscall/src/task.rs`中的`sys_task_suspend_token`函数），返回`Poll::Ready`并从内部取出`ctx: UserContext`（那么是什么时候放进去的？上面提到在创建`Thread`的时候已经对这个`ctx`进行了初始化）；否则将顶层Future的Waker放到当前`Thread`里面并返回`Poll::Pending`。也就是说，目前这里看不出有基于时间片长度进行的抢占式调度或是手动yield，只是从线程控制块中取出用户上下文，同时特殊处理某个系统调用。要想搞清楚调度的话可能还需要看一下底层的Preemptive Scheduler库。（PS:我记得有跟时间片相关的Future来着，等找到了再说）
  
  继续回到`run_user`的实现，后面是对可能的信号进行处理，我们暂且跳过。再接着是切换回用户态的魔法操作`ctx.enter_uspace`。从异步协程的角度来看这是一个同步操作，也就是`ctx`以某种方式改变了自身。不过我们可以再稍微回顾一下具体流程。注意我们从`thread.wait_for_run().await`中拿到的`ctx`应该是在堆上，因为返回的类型是`Box<UserContext>`。与之对应的是，线程控制块中的`context`类型也是`Option<Box<UserContext>>`。`UserContext`实际上来自于`kernel_hal::context::UserContext`。在`kernel-hal/src/common/context.rs`中可以看到：
  
  ```rust
  use trapframe::UserContext as UserContextInner;
  
  #[repr(transparent)]
  #[derive(Clone, Copy)]
  pub struct UserContext(UserContextInner);
  
  impl UserContext {
      /// Switch to user mode.
      pub fn enter_uspace(&mut self) {
          cfg_if! {
              if #[cfg(feature = "libos")] {
                  self.0.run_fncall()
              } else {
                  self.0.run()
              }
          }
      }
  }
  ```
  
  可以看到这里的`UserContext`只是`trapframe` crate提供的`UserContext`的封装，根据是否以libos模式运行调用不同的底层函数，如果是的话调用`run_fncall`，否则在裸机上则调用`run`。以我们比较熟悉的RISC-V架构为例：在`trapframe-rs/src/arch/riscv/trap.rs`中看到`UserContext::run`调用了`run_user`方法，参数为自身的可变引用。`run_user`函数是在同目录下的`trap.S`中用汇编实现的，首先在内核栈上原地保存被调用者保存寄存器，然后将内核栈栈顶保存到`sscratch`寄存器中。之后从提供的`UserContext`地址恢复用户态上下文并最终执行`sret`指令回到用户态。其间并未看到有关页表的操作，说明zCore的设计应该没有考虑到KPTI。
  
  当在用户态执行了一段时间之后，用户态会Trap到内核态，此时应该跳转到`trap.S`中的`trap_entry`函数。这是在什么地方初始化的呢？考虑应该是`trap.rs`中的`init`函数中将`stvec`寄存器设置为`trap_entry`的地址。那么`init`函数是在何处调用的？虽说暂时找不到但是肯定在什么地方被调用了QAQ。在`trap_entry`中不出意料应该将通用寄存器覆盖到`UserContext`中然后从内核栈上恢复`run_user`（指上面那个`async fn`）的上下文。回来之后我们会看到`ctx`的内容已然发生了变化。因此，从内核的视角来看，`ctx.entry_uspace()`毫无疑问是一个同步操作，内核部分的上下文就保存在`sscratch`寄存器中。
  
  再来就是重头戏`handle_user_trap(&thread, ctx).await`，所有中断/异常/系统调用都在里面处理。这里就有一个小问题：此前了解到zCore的内核态应该是打开中断的，那么在这里应当有所体现。于是先来看一下实现。
  
  ```rust
  async fn handle_user_trap(thread: &CurrentThread, mut ctx: Box<UserContext>) -> ZxResult {
      let reason = ctx.trap_reason();
      if let TrapReason::Syscall = reason {
          let num = syscall_num(&ctx);
          let args = syscall_args(&ctx);
          ctx.advance_pc(reason);
          thread.put_context(ctx);
          // 创建syscall实例
          let mut syscall = linux_syscall::Syscall {
              thread,
              thread_fn,
              syscall_entry: kernel_hal::context::syscall_entry as usize,
          };
          trace!("Syscall : {} {:x?}", num as u32, args);
          // 异步对系统调用进行处理，注意在处理过程中打开中断，因此也要留心关中断锁的使用
          run_with_irq_enable! {
              let ret = syscall.syscall(num as u32, args).await as usize
          }
          // 将系统调用返回值写入UserContext中
          thread.with_context(|ctx| ctx.set_field(UserContextField::ReturnValue, ret))?;
          return Ok(());
      }
  
      thread.put_context(ctx);
  
      let pid = thread.proc().id();
      match reason {
          TrapReason::Interrupt(vector) => {
              // 这里是允许中断嵌套的(也就是说应该支持中断的抢占了)，同时中断处理是在kernel_hal中完成的
              run_with_irq_enable! {
                  kernel_hal::interrupt::handle_irq(vector)
              }
              // 裸机模式下进行基于时间片的抢占式调度，调度在整体的runtime中，而runtime是由kernel_hal负责的
              // libos下面因为只能运行一个应用，因此这样做没有意义？还是不支持？
              #[cfg(not(feature = "libos"))]
              if vector == kernel_hal::context::TIMER_INTERRUPT_VEC {
                  kernel_hal::thread::yield_now().await;
              }
              Ok(())
          }
          TrapReason::PageFault(vaddr, flags) => {
              warn!(
                  "page fault from user mode @ {:#x}({:?}), pid={}",
                  vaddr, flags, pid
              );
              // 获取当前进程的vmar并开始处理page fault，注意这个过程中是不开中断的
              let vmar = thread.proc().vmar();
              vmar.handle_page_fault(vaddr, flags).map_err(|err| {
                  error!(
                      "failed to handle page fault from user mode @ {:#x}({:?}): {:?}\n{:#x?}",
                      vaddr,
                      flags,
                      err,
                      thread.context_cloned(),
                  );
                  err
              })
          }
          // 目前比较简单粗暴，其他的Trap类型均不支持
          _ => {
              error!(
                  "unsupported trap from user mode: {:x?}, pid={}, {:#x?}",
                  reason,
                  pid,
                  thread.context_cloned(),
              );
              Err(ZxError::NOT_SUPPORTED)
          }
      }
  }
  ```
  
  好的，那就初步梳理到这里。

