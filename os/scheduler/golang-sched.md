参考文献：

* [Go语言原本之并发调度](https://golang.design/under-the-hood/zh-cn/part2runtime/ch06sched/)
* [Why goroutines instead of threads?](https://go.dev/doc/faq#goroutines)
* 一些系列文章：[[1]](https://cloud.tencent.com/developer/article/1412488),[[2]](https://cloud.tencent.com/developer/article/1412489),[[3]](https://cloud.tencent.com/developer/article/1416867),[[4]](https://cloud.tencent.com/developer/article/1416868)
* [一篇论文 Analysis of the Go runtime scheduler](http://www1.cs.columbia.edu/~aho/cs6998/reports/12-12-11_DeshpandeSponslerWeiss_GO.pdf)
* [一个PPT The Scheduler Saga](https://speakerdeck.com/kavya719/the-scheduler-saga)

为什么忽然突发奇想来看一下Go语言的调度器呢，因为同样是用户态的调度库，感觉这个能更多的借鉴到工作中。相比来说，基于Rust的Tokio也很好，但是我们目前应该还不太会涉及到异步IO，而且C语言中显然也不支持async/await关键字以及stackless coroutine，如果手写状态机的话感觉收益也不明显。所以说Golang中的这个scheduler倒是可以研究一下。

## 设计文档与源码

设计文档：https://golang.org/s/go11sched

源码：https://go.dev/src/runtime/proc.go

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

一句话总结的话：当最后一个自旋的worker结束自旋状态（意味着此时有空闲的P且有G就绪）的时候，会额外unpark一个worker。这样期望能够做到M的按需复始（unpark）。

从数据结构来看，调度用的g0的指针是保存在m中的，还记录了是否处于自旋状态。

看到调度器`sched`结构之前。

## 系列文章

系列文章[3]讲的不错，直接列出了很多策略，这样可以看看哪些我们可以用起来。

数据结构是这样的：每个P都有一个G的本地队列，同时还有一个G的全局队列。之所以存在P的本地队列，大概是为了降低所有核都去抢全局队列的锁竞争开销，同时也更容易保证CPU亲和性。同时，每个P还有一个正在运行的G（非常类似Processor state这种东西），如果一个M，也就是一个worker thread获取到了P，那么它会去跑那个正在运行的G。

规则1：如果M1获取到P1开始跑G1，然后G1创建了G2，那么G2会优先加入到P1的本地队列。

规则2：当一个G退出（通过goexit）的时候，M上运行的G会被切换为一个专用于调度的G0，这个G0会首先从当前P的本地队列中找可运行的G。

规则3：当不断的创建G使得当前P的本地队列满载的时候，进行负载均衡：将当前P本地队列中一半的G移动到全局队列。

规则4：当创建G的时候，运行的G会尝试唤醒其他空闲的P和M，它们会尝试获取G并执行。比如说，M2获取了P2，并运行P2上面的调度协程G0。如果此时没有可执行的G，这里的M2会变成自旋线程。

规则5：偷任务：在上面的情况下，M2会从G的全局队列偷一部分G到P2的本地队列，但是出于负载均衡的目的不能太多也不能太少。如果G的全局队列为空，那么就要从某个P的本地队列偷一半G过来。

规则6：希望一个G新创建的时候立即就能有一个M运行它。但是如果一个M一直在自旋的话会浪费大量CPU资源。因此，规定系统中最多有GOMAXPROCS（也就是最多有多少个P，从OS的层面应该是说我们最多可以**同时**使用多少内核级线程，即最大并发度）个自旋的线程。多余的M，假如自旋一段时间之后仍然没有G，就会进入休眠状态。

规则7：当在执行某个G的时候进行了阻塞的系统调用，则M和P立即解绑，当前M随着上面跑的G一起进入阻塞。然后，P会尝试寻找一个新的M，如果P的本地队列或者全局队列有G，而且还有空闲的M，P会立即唤醒这个M并绑定。（有一个问题：如果M想进入自旋状态，是否需要获取到P？答：应该是不用的，M自旋正是为了获取一个P）否则这个P会加入到空闲P列表，等待某个M获取它并执行。

规则8：当在执行某个G的时候进行了非阻塞系统调用，M和P也会解绑，但M会记住P。当系统调用返回的时候，M会优先判断P是否空闲，如果非空闲的话再自旋找其他P，如果再没有的话则将G加入到全局队列。

规则9：go1.12实现了goroutine的非强制性抢占，也就是一个goroutine运行一定时间之后会收到一个抢占请求。







