# 简单实现

将启动栈、中断栈、Processor、tp 复制多份，每个 hart 自己内部进行调度。

当要加入 thread 的时候，优先加入当前没有执行线程的 hart，如果都在执行的话，随机加入一个。

所有 hart 启动后都直接运行 IDLE 线程，IDLE 线程现在仍可以是循环 wfi 的工作，每到时钟中断就尝试 prepare_next_thread 一下。

# 多核改动

1. 为每个 hart 设置一个启动栈；
2. 定义每个 hart 的 thread-local storage 内容如下：将 hartid 保存在 tp 寄存器中；一个中断栈 KernelStack；一个 current_thread `Option<Arc<Thread>>`。
3. hart0 首先进行原先所有的初始化，同时其他 hart 被阻塞。待 hart0 完成初始化工作之后，通过 ipi 唤醒其他 hart，随后包括 hart0 在内的所有 hart 对于它们的 thread-local storage 进行初始化。
4. 方便起见，外部中断只有 hart0 能收到。
5. 多个 hart 共享一个线程池，内含一个调度队列 scheduler 和一个休眠队列 sleeping_threads，姑且叫做 ThreadPool。它相当于把原来的 Processor 去掉了 current_thread 域。

## 测试多核带来的性能提升

# 具体实现

包装一个当前 hart 执行情况的 HCB (Hart Control Block)?里面包含以下内容：

1. 内核栈 KernelStack
2. 当前执行的线程id `Option<Arc<Thread>>`
3. idle 线程 `Arc<Thread>`

目前还没想到其他内容。该 HCB 需要每个 hart 一份。

IDLE 线程的话，貌似也不太能 wfi 了？

现在的情况是中断处理和 idle 线程的调度傻傻分不清。

中断处理做了太多的事情，比如刚进来的时候就看当前线程是不是结束了；之后就是如果是时钟中断的话还需要进行一波切换。

现在 idle 线程也只有一个 wfi，在它的 TCB 里面当然也有中断上下文，回去之后继续 wfi 罢了。这样想来的话，应该还是可以 wfi。

每个 hart 的 prepare_next_thread 可以设计为抢占底层的 schedule queue，全部木大应该还是要保留一下的，panic 也不用动。

现在的问题大概是，如果 shell 被阻塞在 hart1 上面，串口中断却是在 hart0 上收到，那恐怕 hart1 永远不会被唤醒。应该说 wfi 本来就有点问题。

经典模型：每个 hart 在一个 idle 线程里面循环抢线程来执行，就是在循环开头抢一下，如果能行的话就切换过去，切换回来的时候继续从 idle 线程入口点开始，如果抢不到的话它反正也没事干，就直接继续回到循环开头就可以。所有的 hart 共享调度队列。

我们来思考一下在单核情况下为什么没有就绪线程的话就需要 wfi。这是因为中断是唯一可能产生就绪线程的方式。

但是在多核情况下这不成立。因为其他 hart 上的中断会产生一个所有 hart 上均可运行的就绪线程。所以最好的办法就是在 idle 线程里面忙等待硬抢。只要抢到了就换。有一个奇妙问题与时钟中断相关。在中断之外的地方，与调度相关的地方我们必须把时钟中断关掉，不然有可能产生死锁或者其他问题。

应该只要改动这个就可以了吧？

接下来只有两个问题需要解决：时钟中断和 idle 线程到底都在干什么，以及如何定义线程切换。

*我们先基于 v3 跑起来，哪怕丑陋一些，然后再重构基于 v2 的版本！*

现在的设计是，线程切换和中断完全挂钩，不靠中断根本切换不了...那我也忍了，idle 线程里面只需要一个 loop 了。这样它会每触发一次时钟中断尝试去调度队列里面抢一下。

嗯，这样的话时钟中断就不用动了。线程切换看起来也不用动了，因为终究都是中断上下文的切换。

于是 `Processor` 里面保存 HCB；新增一个 `ThreadPool` 维护全局的调度队列。纯粹与调度有关的不用动，将 `park_current_thread` 和 `prepare_next_thread` 中的 KernelStack 替换成 thread-local 的即可。

看上去应该就行了...?

*一个不错的测例：并发进程间通信！很可惜还是没有什么外设能用...*

### 串口中断无法触发 on qemu

看一眼 qemu 初始化的时候都干了什么。

首先是在 PLIC target1 上设置了编号为 10 的中断源的 Interrupt Enable。

随后将编号为 10 的中断源的优先级设置为 7。

最后将 target1 的中断阈值设置为 0。

这里的 target 应该是从 hart0-m, hart0-s, hart1-m, ... 类推。

随后是串口自身的设置。qemu 里面用的是 16550A，是设备寄存器比较复杂的那种。这鬼东西是来自于第二版吗？完全看不懂在干什么。[这里](http://caro.su/msx/ocm_de1/16550.pdf)可以找到一份 16550A 的文档。MCR 看不太懂，但是从 ICR 可以看出接收端中断的确是打开了的。多核情况下应该也没有什么问题的...它还是应该能在 hart0-s 上接收到串口中断。但是中断那里却没有打印。那么可能的原因就是中断被屏蔽掉了。即 sstatus.sie=false 了。 那么，要么此时已经在中断里面卡死了，要么是在 `Lock<Processor>` 里面。

打印了一些调试信息，发现第一次 sys_read 还没返回就已经卡死了。最后是死在 scheduler 里面移除当前线程的时候，可能是堆出了点问题。把调度算法换一下试试看。

### 各种爆栈、内核堆分配错误

发现如果将内核栈进一步缩小的话，就不会在 idle 线程上下文存储的地方 panic 了，而是会卡死在 sys_read 上面。这也是挺奇怪的...最大的问题在于收不到串口中断。简单 debug 一下发现是堆炸了，表现在 scheduler 将线程从就绪队列转移到阻塞队列里（sys_read）的时候。但是目前我们好像没有什么办法来调试 buddy_system_allocator。

尝试将 LockedHeap 自己包装一层，就可以打印出所有的 alloc 和 dealloc 请求了。最后是发现某次 dealloc 的时候卡死了。但是观察卡死前的若干次 alloc 和 dealloc 请求，都是在反复分配回收一个东西，然而最后一次分配出去了，要把它回收的时候就炸了。难道 buddy_system_allocator 有点问题？

仔细把 alloc/dealloc 前后 LockedHeap 的状态都打印出来，发现某一次 dealloc 之前 LockedHeap 的元数据突然不对了，猜想可能是已经爆栈了。于是我们将栈开大一点试试。但是开大之后仍然没有解决问题。令我非常怀疑的一点是 alloc/dealloc 全程没有修改 total。也就是说这个 bug 基本可以确定和 LockedHeap 的实现无关。

传给 LockedHeap 的起始位置是 $\mathtt{0xFFFF\_FFFF\_8036\_F000}$，可用的大小我给了很大，目前是 $\mathtt{0x200\_0000}$。也就是说直到 $\mathtt{0xFFFF\_FFFF\_8236\_F000}$ 都是可用的。但是我却在分配的东西里面看到了超过 $\mathtt{0xFFFF\_FFFF\_8236\_F000}$ 的位置？难道我要成为 debug 先锋了？

debug 了一通之后发现 LockedHeap 并没有分配越界。

这次奇怪的分配发生在：

```rust
into processor_main!
some alloc/deallocs...
switch to idle!
triggered interrupt Interrupt(SupervisorTimer) on hart 0
dealloc request ptr = 0xffffffff803755e0 layout = Layout { size_: 24, align_: 8 }, heap = Heap { user: 18446744071564530884, allocated: 0, total: 1 }
triggered interrupt Exception(LoadPageFault) on hart 0
```

找了一下，这个 803755e0 的 alloc 恰好发生在 getting context 之前，也就是在将 user_shell 线程 add 到 THREAD_POOL 的时候。分配的 24 字节很可能代表一个 `Arc<Thread>`。

是在切换到 idle 线程之后，然后它应该是在死循环，触发了一次时钟中断，然后时钟中断里面会进行调度：`park_current_thread` 以及 `prepare_next_thread`。park_current_thread 就是把中断上下文 store 到 idle 的 TCB 里面，这一步堆分配器没有参与；然后 prepare_next_thread 的时候，通过一番 debug 好像是死在 scheduler.get_next 了。这个时候需要把一个 `Arc<Thread>` 从 scheduler 队列里面 pop 出来，然后就会触发奇怪的 dealloc。进行了一下精确定位，发现 803755e0 的 alloc/dealloc 都和 scheduler 有关，分别代表将 user_shell 线程加入调度队列和从调度队列中移除。但是分配的时候可以回收的时候就炸了？？？这是什么道理呀。

尝试了一下把 LinkedList 换成 VecDeque，时间复杂度不变，但是这回至少在这个地方没有奇怪的问题了。

但是后面又出现了奇怪的问题：

```rust
switch to idle!
triggered interrupt Interrupt(SupervisorTimer) on hart 0
into qemu::supervisor_timer!
Heap { user: 546920, allocated: 548584, total: 33554432 }
into outer park_current_thread!
Heap { user: 546920, allocated: 548584, total: 33554432 }
into outer prepare_next_thread!
Heap { user: 546920, allocated: 548584, total: 33554432 }
into processor::prepare_next_thread
Heap { user: 546920, allocated: 548584, total: 33554432 }
thread_pool lock acquired!
Heap { user: 546920, allocated: 548584, total: 33554432 }
get a thread from thread_pool
into processor::prepare_thread
Heap { user: 546920, allocated: 548584, total: 33554432 }
into thread::retrieve_context
Heap { user: 546920, allocated: 0, total: 0 }
into KernelStack::push_context!
exit processor::prepare_thread!
triggered interrupt Interrupt(SupervisorTimer) on hart 0
into qemu::supervisor_timer!
Heap { user: 1, allocated: 0, total: 0 }
into outer park_current_thread!
Heap { user: 1, allocated: 0, total: 0 }
into outer prepare_next_thread!
Heap { user: 1, allocated: 0, total: 0 }
into processor::prepare_next_thread
Heap { user: 1, allocated: 0, total: 0 }
thread_pool lock acquired!
Heap { user: 1, allocated: 0, total: 0 }
get a thread from thread_pool
into processor::prepare_thread
Heap { user: 1, allocated: 0, total: 0 }
into thread::retrieve_context
Heap { user: 1, allocated: 0, total: 0 }
into KernelStack::push_context!
exit processor::prepare_thread!
triggered interrupt Interrupt(SupervisorTimer) on hart 0
```

可以看到打印 heap 的状态信息的时候，allocated 和 total 突然变成 0 了。后来把所有东西打出来之后，发现内核栈开小了...我的天。*看来在之后写书的时候还需要特别说明一下一些重要的数据结构的大小设置，不过这件事情可远比说说要复杂多了*。

现在终于回到了 idle 线程的问题。

```rust
syscall_id = 64
Rust user shell
triggered interrupt Exception(UserEnvCall) on hart 0
syscall_id = 64
>> triggered interrupt Exception(UserEnvCall) on hart 0
syscall_id = 63
into sys_read!
inode got!
try read into buffer!
into stdin::read_at!
no data ready in buffer!
ready push current_thread into condvar queue!
sleep_current_thread!
into thread_pool::sleep_thread!
ready remove thread from scheduler!
ready insert thread into sleeping_threads!
inode.read_at returned!
SyscallResult::Park!
SyscallResult::Park
ready park_current_thread!
return prepare_next_thread!
prepare IDLE_THREAD!
triggered interrupt Interrupt(SupervisorTimer) on hart 0
src/process/thread.rs:54: 'assertion failed: self.inner().context.is_none()'
```

事情是这样的：user_shell 线程通过 sys_read 进入内核态，保存了中断上下文，然后查询 stdin 发现没有字符，于是在条件变量里面将当前线程加入等待队列，然后休眠当前线程，就是把当前线程从 HCB 里面取出，并在 scheduler 里面将其从就绪队列转移到休眠队列。接着发现 syscall 返回值是一个 park，于是先 park_current_thread 将中断上下文保存在 user_shell 线程的 TCB，然后 prepare_next_thread，注意这个时候 scheduler 里面是没东西的，但是休眠队列里面有东西，于是就先把 idle 线程的 TCB 取出，弄到中断栈上。这样 trap 返回之后就会回到 busy_loop 里面了。

注意这个时候 idle 线程的 TCB 应该没有中断上下文的。本来接下来的时钟中断，我们要先 park_current_thread 将当前的中断上下文保存在 idle 线程的 TCB 里面，这时我们期望它这个位置是空的。但是为什么又有了呢？重点在于我们 prepare_next_thread 的时候是直接搞了一份 idle 线程的 clone。

### 给每个 Process 一个自己的 idle thread

这个肯定是必要的。也很简单。

### 真正将多核跑起来

通过在时钟中断处理时 sie::clear_stimer 可以让每个 hart 上的 idle thread 都只会触发一次时钟中断。而后发现进入时钟中断之后 hartid 全部变成 0 了？大概想了一下，应该是在中断上下文里面被覆盖了 QAQAQQQ。

于是现在的做法是 x3（gp） 和 x4（tp） 就不保存和恢复了。

接下来的问题是：

```rust
triggered interrupt Interrupt(SupervisorTimer) on hart 1
triggered interrupt Interrupt(SupervisorTimer) on hart 0
triggered interrupt Interrupt(SupervisorTimer) on hart 2
context = 0xffffffff82384150 on hart 3
triggered interrupt Interrupt(SupervisorTimer) on hart 3
thread_pool lock acquired! on hart 0
thread_pool lock acquired! on hart 3
triggered interrupt Exception(UserEnvCall) on hart 0
src/process/thread.rs:52: 'called `Option::unwrap()` on a `None` value'
```

看来之前担心的问题确实出现了。也就是说 user_shell 线程 hart0 执行了，却还保留在就绪队列中，然后被 hart3 又抢到了，这就炸了。

因此，我们需要对调度算法进行修改~这回我们要确实的保证每个 hart 只会出现在某个 Processor 的 current_thread、ThreadPool 的 Scheduler 和 sleeping_threads 三个地方中的一个。

主要就是 park_current_thread+prepare_next_thread 吧。 最大的问题是 scheduler::get_next（比如 FIFO）里面是 pop_front 然后 push_back，这样是不行的。我们不要让它在这个时候放回去，而是要在 prepare_next_thread 更换 current_thread 之前把它放回 scheduler 里面去。另外我们应该用不到 remove_thread 了。它发生在 sleep_current_thread 的时候，但我们只需将其丢进 sleeping_threads，然后替换掉 current_thread 即可。

另一件事是关于 idle 线程的处理。我们决不能让 idle 线程进入 scheduler。回想一下，idle 线程为何没有被回收？对了，我们是把它挂在 Processor 下面一个固定的位置的。

这样做之后又有问题：之前 prepare_next_thread 的判断是调度队列和休眠队列里都没有线程就直接 panic，但是在多核情况下很有可能线程的总数比核数要少。所以将这个判断去掉。

然后好像稍微能跑一点了，但是跑了各个用户程序都有问题，手动滑稽。

又尝试跑了一次 hello_world，居然没崩...但是我观察到一个问题：

```rust
Rust user shell
>> hello_world
searching for program hello_world
Hello world from user mode program!
thread 6 exit with code 0
Process 3 exited
pid = 3
```

有点搞不清楚 pid = 3 是什么地方输出的。有点奇怪。这个应该是忘了更新用户程序导致的。

然后，连续跑两次 hello_world，总是第一次能跑，第二次就：

```rust
>> hello_world
searching for program hello_world
Hello world from user mode program!
thread 7 exit with code 0
Process 3 exited
src/process/processor.rs:157: 'called `Option::unwrap()` on a `None` value'
```

后来发现对于将当前线程重新放回调度队列的处理有点问题。于是分离出了一个新的 run_current_thread_later 函数，会在每次时钟中断的时候判断如果当前线程不是 idle ，就把当前线程放回调度队列里面。

然后惊奇的发现，如果第一个用户程序是 fantastic_text 的话就能跑的很好，完全看不出有什么问题。第一个是 hello_world 的话就会在 hello_world 退出之后卡死。因为 hello_world 很短，应该是来不及跨越时钟中断的。研究了一下，问题出在 hello_world 退出之后，user_shell 才调用 wait，那自然是无法唤醒的了。

于是暂时还是把两个 syscall 先合并了。

看起来可以跑了，芜湖起飞！

又发现了之前的一点小 bug，就是在堆分配器里面会做一些确保堆分配器工作的 assertion，然而当时我并没有意识到多核情况下很可能是不成立的。删掉之后就能跑了。

### 为每个线程保存它们曾跑在哪个 hart 上

这样就可以很好地体现多核了。

这个比较简单，只需要在每次 prepare_next_thread 的时候将当前的 hartid 加入到一个 vec 里面即可。

既然如此，我们需要确定什么情况下有可能出现线程切换。

1. 时钟中断的时候，首先 park_current_thread 然后 prepare_next_thread，只需在 prepare_next_thread 的时候处理即可。
2. 其他中断的时候，如串口中断。一定在 hart0 上收到，但是唤醒的线程需要其他 hart 再去抢，不一定在 hart0 上执行。这个时候它只是将 context 原样返回给 __restore 而已。
3. syscall 的时候，也只有被阻塞的时候才会 sleep_current_thread 其次 park_current_thread 最后 prepare_next_thread。当然还有一个特殊的 kill syscall，它是 kill_current_thread+prepare_next_thread。

也就是说，只有线程出于某些原因不能再向下执行，将自身从 current_thread 放回到 scheduler 的队尾或者休眠队列的时候，才会出现 prepare_next_thread。

我们想实现的终极功能是：统计一个线程的 kernel/user 使用 CPU 时间占比，以及每个 core 的时间占比。

这挺像是我最近遇到的最像算法的问题了，好好想想给个解决方案。

*Prologue:* 当一个线程被 prepare_next_thread 选中，表示它的一段**固定在某个 hart 上的**执行历程已然开始。
*Epilogue:* 当一个线程被 prepare_next_thread，表示它的一段**固定在某个 hart 上的**执行历程结束。

目前，*Prologue* 和 *Epilogue* 不能跨越时钟中断。

在 *Prologue* 和 *Epilogue* 中间，可能会出现若干次不会触发 prepare_next_thread 的 trap，导致用户态时间-内核态时间这种模式不断重复。啊这家伙好难实现。我们先把多核跑起来再说吧。

最后也实现完了。还将所有的输出打包到一起，并加上了一点美化。	

### 实现 wait4 系统调用

目标：user shell 不再 one-shot

注意到 wait 系列 syscall 都是从进程的角度进行考虑的。然而现在我们的实现中进程连 id 都没有...就算加上了进程，我们可以 wakeup 它的第一个线程即可。但是从内存回收的角度，我们知道 Process 是挂在 Thread 下面的，等等，真的是这样的吗？

`Process` 下面挂着 `MemorySet`，它可以负责回收所有的（包括存储页表和存储进程地址空间）的物理页帧；

而 `Thread` 下面挂着 `Process` 和一个上下文 `Context`；

那么 `Thread` 又挂在哪里呢？可以说是挂在 `Processor` 还有 `ThreadPool` 两个地方。当它结束的时候，这两个地方都没有指向它的 `Arc`，于是它就会被自动回收啦！这还蛮巧妙的，回收掉 `Thread` 之后，`Process` 的引用计数会变成 0，于是我们又会去回收 `Process`。也就是说，**Process 确实比 Thread 后回收**。

因为目前这种情况的话是不存在子进程这种东西的...

我们需要注意 wait4 和 clone 以及 execve 三个 syscall 的实际语义，然后进行简化实现。

唉这个东西优先级低一点吧，我们先跑起来再说。

写了一段时间之后，发现了一个死锁的问题。

在用户程序调用 sys_exit 退出之后，会在某个地方调用 kill_current_thread 把当前线程移除，然而问题在于这会移除两个地方，一是 Processor 里面的 current_thread，二是 ThreadPool 里面的 scheduler。如果我们按照这个顺序的话，会在持有 ThreadPool 锁的情况下将当前线程 rc 清零，然后进而触发 Process 的回收，会唤醒终端线程，这又会用到 ThreadPool 的锁，就死锁了。**我们暂时可以调整移除的顺序来规避死锁问题，但是更好的办法是让 `Arc<Thread>` 只出现一次。**

这一步暂时宣告完成。√

### 实现 gettimeofday 系统调用

目标：可以通过执行时间来比较性能

### k210

把 qemu 跑通之后，我将平台换成 k210 希望能直接跑通，但显然这是不可能的 QAQ

很有可能是爆内存了。

原先 Qemu 的情况是 4 核，内核栈的大小 16KiB，运行栈大小 32KiB，内核堆 32MiB，启动栈每个 1MiB。这个已经能正常把 master 上的代码在多核上跑了。

然后 K210 的情况目前是双核，内核栈大小 32KiB，运行栈大小 32KiB，内核堆 3MiB，启动栈还是沿用 Qemu 的 1MiB，这个就太大了。暂时先改成 64KiB。这样总大小是 3MiB+(32+64KiB)*2=3.1875MiB。

发现原来的 clear_bss 会占用更多的栈空间？这挺反直觉的。

某个时候 k210 多核跑通了...但是之后就一直总跑到 unreachable 那里去???

先回滚吧，太恐怖了。

# 委曲求全的实现

1. KERNEL_THREAD 和 PROCESSORS 都是手动展开成 4 个，目前非常不优雅。
2. 尝试实现 sys_wait，但是由于没有子进程的设定，这无从展开
3. 由于 pthread 的实现难度实在太大，同步互斥应该还是只能在内核线程里面自己玩了...但是有多核的话还是有点意思的，可以比较性能。

# 碎碎念

现在这个 syscall 看起来比较像异步，但是我们这一版基本上不考虑异步，所以还是改回同步？

那么被阻塞的时候就要将当前的上下文保存到 TCB 中。注意这个线程执行上下文是包括中断上下文的。

我能想到的一种办法就是：在线程切换的时候，将当前的中断栈中**实际**的内容拷贝到 TCB 里面，再从切换到的线程的 TCB 里面把内容读取到中断栈中，...

但是写下去就会发现这东西和每个线程一个运行栈和内核栈是一样的。反正都节省不了内存了，那么我们也大可不必大费周章，直接回滚到第二版就行了。