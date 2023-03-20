参考文献：

* [Go语言原本之并发调度](https://golang.design/under-the-hood/zh-cn/part2runtime/ch06sched/)
* [Why goroutines instead of threads?](https://go.dev/doc/faq#goroutines)
* 一些系列文章：[[1]](https://cloud.tencent.com/developer/article/1412488),[[2]](https://cloud.tencent.com/developer/article/1412489),[[3]](https://cloud.tencent.com/developer/article/1416867),[[4]](https://cloud.tencent.com/developer/article/1416868)

为什么忽然突发奇想来看一下Go语言的调度器呢，因为同样是用户态的调度库，感觉这个能更多的借鉴到工作中。相比来说，基于Rust的Tokio也很好，但是我们目前应该还不太会涉及到异步IO，而且C语言中显然也不支持async/await关键字以及stackless coroutine，如果手写状态机的话感觉收益也不明显。所以说Golang中的这个scheduler倒是可以研究一下。

## goroutines instead of threads

提供更简单的并发模型：基于1:1的内核线程模型，复用这些线程供协程（在这里指goroutine，不过据说goroutine并不完全算是一种协程coroutine）使用。所谓的协程就是一个可以独立执行的函数。

一个关键点是：当线程上的一个协程阻塞（比如开始I/O）的时候，线程上的其他协程会被移动到其他可运行（runnable）的线程上免受牵连。这套机制是对开发者透明的。goroutine有自己的栈，但仅占用数KiB，而且应当可以被动态按需拓展。

为了尽可能控制goroutine的栈开销，go运行时使用可重设大小的、有界的栈。一个goroutine最开始仅会被分配数KiB的栈空间（通常这已经足够了），当不足的时候，这个栈空间可以在运行时动态伸缩。每次函数调用只会产生平均3条指令的CPU开销。这样的话，同地址空间可以创建100,000个goroutine，远比线程更多。

## go原本之并发调度

### 随机调度基本概念

这节是介绍一些理论上的调度算法研究进展。

### work stealing

希望从理论上说明work stealing的优越性而不是拍脑袋。暂时没用。

### MPG模型与并发调度单元

模型三要素：M(Machine)，也就是worker thread，1:1模型的线程；P(Processor)，数量等同于核数，一个worker必须与一个Processor关联才能执行worker上面的goroutine，当然一个Processor上面同时也只能绑定一个worker；G(Goroutine)，即复用worker的用户态有栈协程。