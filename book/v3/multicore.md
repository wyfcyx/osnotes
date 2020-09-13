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

