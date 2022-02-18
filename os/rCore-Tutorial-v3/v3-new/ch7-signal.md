通过 `kill(usize pid, i32 signum)=129`可以向进程`pid`发送信号`signal`。

通过 `sigaction(i32 signum, *const _ sighandler)=134`可以为对应的信号设置handler，事实上后一个参数（标准是两个参数，将原来的设置load到本地同时将新的设置上传给内核）是一个结构体，除了设置为某个特定的handler之外，还可以设置为使用默认handler或者忽略该信号。

通过`sigreturn=139`可以从信号handler退出并回到应用的正常执行。

信号可以通过`kill`从一个进程传给另一个进程(如`SIGINT=2`)，也可由进程自身的执行产生（如`SIGILL=4`以及`SIGSEGV=11`或是`SIGFPE=8`又或`SIGABRT=6`），或是由内核生成传给进程（如`SIGPIPE=13`意味着尝试写入一个没有读者的管道，`SIGALRM=14`用途不明），以及用户自己定义的信号比如`SIGUSR1/SIGUSR2`。 

> 通过[`alarm`系统调用](https://www.man7.org/linux/man-pages/man2/alarm.2.html)可以设置固定的时间间隔来让内核发给当前进程一个`SIGALRM`信号。进程则可以通过`sigaction`系统调用来设置收到该信号时调用的handler。
>
> 不过，handler的机制似乎有些难以设计。可能需要给每个trap handler维护一个trap context而不能用进程自身的trap context，因为里面还保存着收到信号之前的应用上下文。还有一个大问题是：当用户的信号handler结束之后如何通知内核继续原有的执行。另有一个与之类似的问题：在一个线程入口函数结尾需要手动调用`thread_exit`系统调用的做法很不优雅，应如何避免这种操作？

进程接收到不同信号之后的默认行为：详见[UltraOS文档](https://github.com/xiyurain/UltraOS/blob/main/doc/Signal.md)

---

实现？

先不考虑支持handler，仅支持`kill`系统调用，然后就是`SIGINT/SIGILL/SIGSEGV`这几种信号。结合管道，大概`SIGPIPE`也是有用的，它们的处理都很简单：直接将进程退出就行。

第二步有点想在I/O重定向的基础上实现一个多层管道。直接把所有中间管道创建出来，然后依次fork这些进程，在exec之前完成将I/O重定向到管道就行了，但是需要注意的是读写端口引用计数的维护。

如果最后再有时间的话，再考虑handler，感觉跟多线程不是很容易结合的样子。大概随机选一个线程去执行handler？不过确实还是能实现蛮有意思的东西。