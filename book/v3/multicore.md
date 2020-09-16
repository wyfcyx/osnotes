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

# 碎碎念

现在这个 syscall 看起来比较像异步，但是我们这一版基本上不考虑异步，所以还是改回同步？

那么被阻塞的时候就要将当前的上下文保存到 TCB 中。注意这个线程执行上下文是包括中断上下文的。

我能想到的一种办法就是：在线程切换的时候，将当前的中断栈中**实际**的内容拷贝到 TCB 里面，再从切换到的线程的 TCB 里面把内容读取到中断栈中，...

但是写下去就会发现这东西和每个线程一个运行栈和内核栈是一样的。反正都节省不了内存了，那么我们也大可不必大费周章，直接回滚到第二版就行了。