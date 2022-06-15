这里来整理一下zCore运行时与调度相关的信息。

运行时即硬件抽象层`kernel_hal` crate，其中为`libos`和裸机平台`bare`（包括多种不同的ISA）提供了不同的实现，还有两个平台公共的部分放在`common`子crate中。

`common/thread.rs`中有两个zCore中常用的函数：

```rust
/// Sleeps until the specified of time.
pub async fn sleep_until(deadline: Duration) {
    SleepFuture::new(deadline).await
}

/// Yields execution back to the async runtime.
pub async fn yield_now() {
    YieldFuture::default().await
}
```

这两个Future则来自于`common/future.rs`中：

```rust
#[must_use = "`yield_now()` does nothing unless polled/`await`-ed"]
#[derive(Default)]
pub(super) struct YieldFuture {
    flag: bool,
}

// 比较简单，即第一次Poll的时候返回Pending，第二次Poll的时候返回Ready
// 但是这里需要注意Waker的使用，一般情况下我们在这里应该将传入的Waker注册到相应的句柄上，然后由某个Reactor调用唤醒方法；但这里我们是直接调用的，这个与底层的Executor和Reactor具体实现有关
impl Future for YieldFuture {
    type Output = ();

    fn poll(mut self: Pin<&mut Self>, cx: &mut Context) -> Poll<Self::Output> {
        if self.flag {
            Poll::Ready(())
        } else {
            self.flag = true;
            cx.waker().wake_by_ref();
            Poll::Pending
        }
    }
}

#[must_use = "`sleep_until()` does nothing unless polled/`await`-ed"]
pub(super) struct SleepFuture {
    deadline: Duration,
}

impl SleepFuture {
    pub fn new(deadline: Duration) -> Self {
        Self { deadline }
    }
}

// 这里就比较正常，在Pending之前在Reactor中注册传入的waker
impl Future for SleepFuture {
    type Output = ();

    fn poll(self: Pin<&mut Self>, cx: &mut Context) -> Poll<Self::Output> {
        if timer::timer_now() >= self.deadline {
            return Poll::Ready(());
        }
        if self.deadline.as_nanos() < i64::max_value() as u128 {
            let waker = cx.waker().clone();
            timer::timer_set(self.deadline, Box::new(move |_| waker.wake_by_ref()));
        }
        Poll::Pending
    }
}
```

`YieldFuture`主要用于时间片用尽后对当前任务进行抢占式调度，比如在`loader/src/linux.rs`中的`handle_user_trap`中能够看到这样的代码：

```rust
TrapReason::Interrupt(vector) => {
    run_with_irq_enable! {
        kernel_hal::interrupt::handle_irq(vector)
    }
    #[cfg(not(feature = "libos"))]
    if vector == kernel_hal::context::TIMER_INTERRUPT_VEC {
        kernel_hal::thread::yield_now().await;
    }
    Ok(())
}
```



顺带一提，`future.rs`中还提供了其他两个Future，分别叫做`DisplayFlushFuture`还有`SerialReadFuture`，这里先略过。

硬件抽象层需要为上层的zCore提供一些底层原语，接口可以在`src/hal_fn.rs`中找到，可以看到分成负责启动的`boot`，与CPU参数相关的`cpu`，物理内存相关的`mem`，虚拟内存相关的`vm`，中断相关的`interrupt`，终端输出相关的`console`，任务相关的`thread`，定时器相关的`timer`，随机数生成器相关的`rand`，以及VDSO相关的`vdso`这些模块。

让我们先关注与任务（单位应该是Future无栈协程而非线程）管理生成相关的`thread`模块：

```rust
/// Thread spawning.
pub mod thread: common::thread {
    /// Spawn a new thread.
    pub fn spawn(future: impl Future<Output = ()> + Send + 'static);

    /// Set tid and pid of current task.
    pub fn set_tid(tid: u64, pid: u64);

    /// Get tid and pid of current task.
    pub fn get_tid() -> (u64, u64);
}
```

其中除了我们需要重点关注的`spawn`函数之外，还有`set/get_tid`两个方法，其中的`tid`和`pid`应该分别指的是线程和进程ID，这个应该在`libos`模式下才会有用吧。

在裸机模式下，`thread`模块各方法的实现可以在`bare/thread.rs`中找到：

```rust
hal_fn_impl! {
    impl mod crate::hal_fn::thread {
        fn spawn(future: impl Future<Output = ()> + Send + 'static) {
            cfg_if! {
                if #[cfg(target_arch = "aarch64")] {
                    executor_origin::spawn(future);
                } else {
                    executor::spawn(future);
                }
            }
        }

        fn set_tid(_tid: u64, _pid: u64) {}

        fn get_tid() -> (u64, u64) {
            (0, 0)
        }
    }
}
```

可以看到，这里`set/get_tid`基本上是空实现，而`spawn`则根据平台不同调用`executor`或`executor_origin`平台提供的`spawn`方法。从`Cargo.toml`中可以看到，对于aarch64平台使用的是原版的`rcore_os/executor`，对于其他平台则使用zyr改造的`PreemptiveScheduler`。我们不妨从这里切入进去看看它的实现：

从目录上可以看到它支持RV64和x86_64两个平台。然后公开了`handle_timeout`，`run_until_idle`，`sched_yield`还有`spawn`这四个方法，它们的实现可以在`runtime.rs`中找到。

先来看`run_until_idle`。在zCore启动代码中我们这样来运行第一个进程：

```rust
if #[cfg(all(feature = "linux", feature = "zircon"))] {
    panic!("Feature `linux` and `zircon` cannot be enabled at the same time!");
} else if #[cfg(feature = "linux")] {
    let args = options.root_proc.split('?').map(Into::into).collect(); // parse "arg0?arg1?arg2"
    let envs = alloc::vec!["PATH=/usr/sbin:/usr/bin:/sbin:/bin".into()];
    let rootfs = fs::rootfs();
    let proc = zcore_loader::linux::run(args, envs, rootfs);
    utils::wait_for_exit(Some(proc))
} else if #[cfg(feature = "zircon")] {
    let zbi = fs::zbi();
    let proc = zcore_loader::zircon::run_userboot(zbi, &options.cmdline);
    utils::wait_for_exit(Some(proc))
} else {
    panic!("One of the features `linux` or `zircon` must be specified!");
}
```

可以看到在创建第一个进程之后调用了`utils::wait_for_exit`，它的实现：

```rust
// 裸机平台
#[cfg(not(feature = "libos"))]
pub fn wait_for_exit(proc: Option<Arc<Process>>) -> ! {
    kernel_hal::timer::timer_enable();
    info!("executor run!");
    loop {
        #[cfg(target_arch = "aarch64")]
        let has_task = executor_origin::run_until_idle();
        #[cfg(not(target_arch = "aarch64"))]
        let has_task = executor::run_until_idle();
        if cfg!(feature = "baremetal-test") && !has_task {
            proc.map(check_exit_code);
            kernel_hal::cpu::reset();
        }
    }
}
```

暂且不讨论LibOS上的实现。对于裸机平台，`run_until_idle`方法便是在这里调用的。从实现的角度来讲，`run_until_idle`相当于Executor的主事件循环：

```rust
// per-cpu scheduler.
pub fn run_until_idle() -> bool {
    debug!("GLOBAL_RUNTIME.run()");
    loop {
        let mut runtime = get_current_runtime();
        let runtime_cx = runtime.get_context();
        let executor_cx = runtime.strong_executor.context.get_context();

        runtime.current_executor = Some(runtime.strong_executor.clone());
        // 释放保护 global_runtime 的锁
        drop(runtime);
        debug!("run strong executor");
        switch(runtime_cx, executor_cx);
        // 该函数返回说明当前 strong_executor 执行的 future 超时或者主动 yield 了,
        // 需要重新创建一个 executor 执行后续的 future, 并且将
        // 新的 executor 作为 strong_executor，旧的 executor 添
        // 加到 weak_exector 中。
        runtime = get_current_runtime();
        if runtime.task_num() == 0 {
            return false;
        }
        // 只有 strong_executor 主动 yield 时, 才会执行运行 weak_executor;
        if runtime.strong_executor.is_running_future() {
            debug!("downgrage strong executor");
            runtime.downgrade_strong_executor();
            continue;
        }
        // 遍历全部的 weak_executor
        if runtime.weak_executors.is_empty() {
            drop(runtime);
            continue;
        }
        debug!("run weak executor");
        runtime
            .weak_executors
            .retain(|executor| executor.is_some() && !executor.as_ref().unwrap().killed());
        for idx in 0..runtime.weak_executors.len() {
            if let Some(executor) = &runtime.weak_executors[idx] {
                if executor.killed() {
                    continue;
                }
                let executor = executor.clone();
                let executor_ctx = executor.context.get_context();
                runtime.current_executor = Some(executor);
                drop(runtime);
                switch(runtime_cx as _, executor_ctx as _);
                runtime = get_current_runtime();
            }
        }
        if runtime.task_num() == 0 {
            return false;
        }
    }
}
```

这里需要补充的是，这里的调度是每个CPU上跑一个runtime，每个runtime被多个Executor复用，这些Executor分为weak和strong两类，strong可以抢占weak（即根据上面的描述，“只有 strong_executor 主动 yield 时, 才会执行运行 weak_executor”）。每个Executor自身有一个事件循环，调度多个Future（无栈协程），因此每个Executor自己是一个线程，有自己的栈。runtime和这些executors之间可以类似于green thread的方式进行切换。

暂时考虑忽略掉weak和strong executor之间的区别，看看`spawn`的实现：

```rust
pub fn spawn(future: impl Future<Output = ()> + Send + 'static) {
    spawn_task(future, None, Some(crate::arch::cpu_id() as _));
}

/// Spawn a coroutine with `priority` and `cpu_id`
/// Default priority: DEFAULT_PRIORITY
/// Default cpu_id: the cpu with fewest number of tasks
pub fn spawn_task(
    future: impl Future<Output = ()> + Send + 'static,
    priority: Option<usize>,
    cpu_id: Option<usize>,
) {
    debug!("try to spawn {:?} {:?}", priority, cpu_id);
    let priority = priority.unwrap_or(DEFAULT_PRIORITY);
    let runtime = if let Some(cpu_id) = cpu_id {
        &GLOBAL_RUNTIME[cpu_id]
    } else {
        GLOBAL_RUNTIME
            .iter()
            .min_by_key(|runtime| runtime.lock().task_num())
            .unwrap()
    };
    runtime.lock().add_task(priority, future);
}
```

这里可以看到，每个核都有自己独立（从调度意义上讲）的一个runtime，并允许通过cpuid进行索引。然后调用runtime的`add_task`方法。