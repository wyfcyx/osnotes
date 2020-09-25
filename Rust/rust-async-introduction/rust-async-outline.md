# Rust async 的理解技术报告大纲

## 先罗列一下要包含进去的内容~

并发场景，意味着资源受限和资源的聪明利用，从 CPU 的角度看，没有一个任务能够完整的从头运行到尾，都必须具有中断的能力。最关键的是消除阻塞（理解为可能带来很重的上下文切换开销）与忙等待（理解为 CPU 资源浪费）。

于是要达成并发，我们可能有哪些做法呢？

1. 线程+忙等待
2. 线程+阻塞（相比 1 减少了 CPU 资源的浪费）
3. 协程+异步（相比 2 减少了内存开销，同时在编译器的极致优化之下可以获得更小的上下文切换开销）

那么该如何理解这一点呢？先来介绍 Rust Future 的整体架构。

Future trait 的核心方法：poll，其中的 Pin 和 Context 是重点介绍对象。

Future 的树形结构，其中 top-level Future 暴露给 Executor，leaf Future 则关系到所谓的 Reactor，当时机成熟之后唤醒 I/O 资源对应的 leaf Future 所在的 top-level Future，让它能继续在 Executor 中被 poll。

唤醒：Context 实际上也就是 Waker，其调用者是 Reactor，实现者是 Executor。

Future 运行时包括 Reactor 和 Executor 两部分。

编译期 Future 状态机的内存布局（低层 Future 状态机被包裹在高层 Future 状态机内）。以及运行时我们能够看到的场景（各个顶层 Future 的状态机被放在堆上，控制权被交给 Executor，栈用来存放一系列 poll 调用链里面开的临时变量。）并以此来解释协程+异步为何占用内存较少，同时为何性能极度依赖编译器的优化。

Future 与生成器 Generator 之间的关系。

Pin 是怎么回事？自引用结构

Context 又是怎么回事？trait Object

具体实现：

主函数与期望输出

将唤醒一个线程（实际上是 Executor 线程）的功能包装到一个 Context 里面去

先 Executor，有一个 Executor 线程，也就是主线程，只有一个 top-level Future

然后 Reactor

最后 Future

总结：使用 Rust async 我们需要做哪些事情？可以依赖哪些社区生态？

下面开始正式的大纲部分。

## 并发

* 描述并发场景，以及我们需要做哪些事情
* 比较不同的解决方案（引入抢占式/非抢占式多任务的概念来进行比较）

## Rust Future

### Future trait

* 核心方法就是 poll 函数。

### Future 树

## 画一些图

divide a async function by await point

async state machine tree

layout of recursively nested async state machine

Executor/Reactor/Waker:

> Poll::Pending -> register a callback pair (I/O Trigger, wake closure of top-level Future)
>
> when I/O Trigger comes, wake closure will be called and the corresponding top-level Future will be able to poll in the executor again

