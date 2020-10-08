# [Consistency Model](https://en.wikipedia.org/wiki/Consistency_model)

感觉 Wikipedia 上面讲的还不错，看一下。

内存一致性模型也就是说系统和程序员之间的一个约定，系统保证当程序员按照规定访问内存的时候，内存是一致的（Consistent），从而对内存进行操作的结果都是可以预测的。强调了 Coherence 和 Consistency 虽然都翻译成一致性，但是 Coherence 是指对于一个固定地址或变量，所有的 Core 都知道与它相关的全局访问序列；而 Consistency 对多个位置的访问顺序能被所有 Core 知道。

有两种方法来定义内存一致性模型以及对它们进行分类：issue 和 view。

* issue 描述一个进程 issue 操作的限制条件；

* view 进程看见的内存操作顺序。

比如，一个模型可能禁止一个进程在之前所有 issued 操作完成之前 issue 一个操作。不同的模型有不同的限制。当一个模型需要另一个模型所有的限制，我们说它比后者更强。

这些模型规定了**底层的硬件如何设计**以及**程序员如何编写代码**，事实上它还会影响到**编译器对指令的重排**。

> 编译器约定一些同步原语，程序员需要理解其语义，并利用它来正确实现并发。
>
> 编译器的优化：在同步原语的约束下，要求编译器对某些同步相关的部分不进行优化。而剩下的代码可以随意优化。既然要翻译成汇编代码，那么就一定要利用架构提供原子指令进行实现。现在我们有汇编代码可以跑了！
>
> 在处理器跑代码的时候，本来会有很多优化，比如超标量执行、乱序执行、多发射等优化来提高 IPC。但是当遇到原子指令的时候，流水线的执行会相应发生一些变化。
>
> 因此，一旦确定了内存一致性模型（Memory Consistency Model），从程序员、编译器和处理器的角度都需要发生某些变化。
>
> 在内存一致性模型确定之后，原子指令会引入 Memory Ordering 的设置。现在我还不太理解 Memory Ordering 是什么意思，但是应该是在内存一致性模型的管理之下。
>
> 此外，现在的处理器内部都存在多级缓存。如何保证不会从缓存中取到错误的数据也是一个问题。因此，在处理器实现的时候，需要通过缓存一致性协议（Cache Coherence Protocol）来保证这一点。虽然目前我还不了解它到底做了什么事情，但是可以看到的是我们程序员并不需要关心它们。[这是](https://en.wikipedia.org/wiki/Cache_coherence)Wikipedia的相关链接。
>
> 事实上，上面这些问题都是因为 SMP 架构共享一个内存。无论模型、协议如何好，总是要面对同一时间只能有一个核访问内存的问题。这也就导致总线带宽成为瓶颈。而 NUMA 架构每个核都可以访问独立的内存，通过通信来共享数据，可能在一定程度上能解决这个问题。我个人还是比较喜欢 SMP，也认为基于 SMP 还有很多事情可以做。

## strict consistency

最严格的模型，任何 Core 对任何变量的写入都需要立刻被所有的 Core 看到。它可以理解为，有一个全局时钟，在时钟周期结束的时候，写入的影响体现在所有 Core 的缓存上。并且下一个操作只能出现在下一个时钟周期内。

它的结果是确定的，但是它只是一种理想模型。因为不存在瞬间到达的通信，并发写入是有可能的。

## sequential consistency

论文原作者的描述："the result of any execution is the same as if the operations of all the processors were executed in some sequential order, and the operations of each individual processor appear in this sequence in the order specified by its program."

大概也就是，所有核都能够看到相同的全局 order，且这个全局 order 对应于每个核的子序列应该遵从核上的代码规定的访问顺序。它的限制有两个重点，分别是**程序顺序**和**原子性**。目前没有时间去深入研究，等之后抽空回来看吧...

参考：[1](https://blog.csdn.net/maokelong95/article/details/80727952)，[2](https://blog.csdn.net/hellochenlu/article/details/51499761)