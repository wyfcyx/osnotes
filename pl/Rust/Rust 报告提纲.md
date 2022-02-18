# PCL Rust 科普准备

## Log

### 2020-11-13

新的风暴又已经来了吗？哭哭哭

大概需要从下面几个方面来进行说明吧，而且基本上在嵌入式的角度，和 C 进行比较。

* 性能方面：包括执行性能和编译性能（指可执行文件的大小）
* 编程方面提供的方便：Rust 自身的语法、库生态
* 相关可用的 IDE/工具

大概总时长需要 1 小时吧。我说这也有点恐怖了。

好。下面开始疯狂收集素材。

### 2020-11-15

陈老师知道了情况之后，和杨沙洲老师讨论了一下，最后决定下周二下午五点给一个 20 分钟的简单宣讲即可。

素材就是陈老师在华为做的长达两个小时报告的 PPT，还有张汉东老师做的《关于 Rust 你需要了解的》讲座，这个我之前看过并留下了详细笔记。

尽管如此，我觉得 cs110L 和 Rust Embedded Book 作为我自身的学习材料仍然是不可错过的，所以今天还是看这些材料，能看多少就看多少。

## 素材-性能比较

[一篇比较 Rust 和 C 性能的 Blog](https://kornel.ski/rust-c-speed)

[另一篇支持 Rust 某种程度上没有那么好的 Blog](https://www.viva64.com/en/b/0733/)

[C++ 和 Rust 的运行性能比较](https://benchmarksgame-team.pages.debian.net/benchmarksgame/fastest/gpp-rust.html)

## 素材-嵌入式 Rust 生态

[awesome-embedded-rust 主页](https://github.com/rust-embedded/awesome-embedded-rust)

> 里面包含很多嵌入式 Rust 的库。

[rtic 官方文档](https://rtic.rs/0.5/book/en/)

[rust embedded book](https://rust-embedded.github.io/book/)

## 素材-不局限于 no_std 的生态

## 素材-Rust 和 C 进行比较

[一篇比较详细的比较 C/Rust 的 Blog](https://medium.com/better-programming/in-depth-comparison-of-rust-and-cpp-579b1f93a5e9)

## 素材-rCore

## 素材-zCore

## 素材-可用的工具

## 素材-陈老师华为 PPT

C 语言的局限性：指针灵活但是非常不安全、缺乏有效的并发支持

当前 OS 的困难 1：内核膨胀，bug 增加，难以发现

比如：内存安全 bg（如使用空指针、use-after-free）、并发相关 bug（如死锁、数据竞争）

当前 OS 的困难 2：不能像开发应用一样开发内核（调试工具缺乏、移到用户态会降低性能）

用高级语言写 OS：Biscuit OS in Golang(2018)，Tock OS in Rust(2017)

[ixy](https://github.com/ixy-languages/ixy-languages) 是一个用多种不同语言开发的网卡的用户态驱动，并进行了性能的比较，这是相关的[论文](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/the-case-for-writing-network-drivers-in-high-level-languages.pdf)。从中可以看出 Rust 和 C 几乎相同（特别是并发程度提高之后）并领先于其他编程语言。

Tsinghua 的尝试：rCore/zCore

## 素材-张汉东老师讲座@上海科技大学

## 素材-张汉东老师知乎 Live

## 提纲（暂定）

### Rust 的诞生背景和设计理念

即可靠性、高性能还有易用性。接下来会分别从这三个方面展开。

Rust 的诞生背景可以参考张汉东老师的讲座或者是《Rust 编程之道》。

顺带可以科普一下 Rust 命名的含义？

老缝合怪 Rust 各向其他语言借鉴了哪些特性？

* 底层内存管理，RAII 从 C/C++ 借鉴
* 类型系统、函数式编程从一些函数式编程语言借鉴

### Rust 的可靠性

内存安全：列举一些经典的 bug，引入所有权模型和借用检查，从裸指针到智能指针（fat pointer），[cs242: Memory Safety](https://cs242.stanford.edu/f19/lectures/06-2-memory-safety)

类型安全：可以说自动隐式转换只有 Deref 一种东西吗？默认情况下检查数组溢出、甚至运算溢出。所以到底什么是类型安全呢？

并发安全：若是要举例的话，Rc 可能是一个不错的例子

错误处理：解决空指针问题：Option；错误处理：Result

安全边界：safe/unsafe，程序员自己承担责任！

### Rust 的高生产力

面向对象：Trait 和泛型，[cs242: Rust Trait](https://cs242.stanford.edu/f19/lectures/07-1-traits)

模块可见性管理

函数式编程：迭代器和闭包

### Rust 的高性能

理论上可能来源于：没有 GC；零成本抽象，运行时比较小。

实战：ixy 和另一个 C/Rust 的 [benchmark](https://benchmarksgame-team.pages.debian.net/benchmarksgame/fastest/rust.html)。至少 C 和 Rust 有着接近且明显超出其他语言的性能，内存占用方面看起来似乎比较大，但是在嵌入式场景下就不一定如此了。Rust 的运行时可以灵活配置。

### Rust 工具集和库生态

（特别是，对于嵌入式开发/系统级编程有哪些好处？）

基于 rustup ，工具链版本集中管理

基于 cargo，语义化版本的包管理器

说到包，那也可以提到目前还算完善的 Rust 生态，包括 Rust 嵌入式生态、rcore-os 系列生态，还有一些其他比较有名的包

嵌入式要提到对于 no_std 的支持，以及 libcore 和 libstd 之间的区别，当然了，还有 alloc 的作用，这个都是应该在上面提到的

很多其他的系列工具：如 clippy，format，rust-doc，自动测试等等功能

写代码的时候有不错的自动补全和类型显示功能，目前常用的是 CLion+内置 Rust 插件或者是 VSCode+rust-analyzer

### C and Rust

Learn Rust based on C

C to Rust/Rust to C

`#[repr(C)]` or `extern "C"` FFI...

### Rust 的不足？

### Thank you!