# CS110L-Spring-2020

这是一门通过 Rust 语言来讲解系统安全的课程。Stanford 于 2020 年春季学期第一次开设。[这里](https://reberhardt.com/cs110l/spring-2020/)是公开的课程页面，内含所有的在线课程视频、课件链接，还有 6 个 Exercises 以及 2 个 Project。第一个 Project 是一个用 Rust 编写一个类似 GDB 的调试器；第二个 Project 则是要实现一个高性能网络服务器，利用 Rust 的多线程工具、async、性能优化（特别是一个负载均衡器来提高 scalability），里面用到了 tokio、async-std、threadpool 等 crates。这些 lab 应该还是很有一刷的必要的。因为这也许可以让我们明白在内核里面可能能做更多的事情。我们可以在[这里](https://github.com/reberhardt7/cs110l-spr-2020-starter-code)找到所有的基础代码。

## [教师感言](https://reberhardt.com/blog/2020/10/05/designing-a-new-class-at-stanford-safety-in-systems-programming.html#)

有空看一看，因为我一直想在书里面加入一个 Rust 快速入门章节的...

## Lecture 01: Introduction

C/C++ 的缺点：比如缓冲区溢出。局部变量中的数组覆盖了栈帧中的 ra ，直接爆炸。此外，一些隐式类型转换，比如有符号到无符号之间的转换很容易出问题（Rust 确实没有这个问题）。我们可以通过 Valgrind 工具来检测错误吗？

为何不使用基于 GC 的语言：GC 的运行时开销较大，而且任何对象都需要由它来管理；GC 发生的时刻不确定，一旦发生所有的线程都需要停止运行；一些针对性的面向缓存的优化会被 GC 破坏掉，或者说，难以调整 GC 的策略来适应内存使用方式的变化。

GC 会带来难以预测的延迟，在很多应用场景中会有严重的问题。

而且，GC 并不能解决数据竞争，仍然会有相关的内存安全问题。

Rust 设计的三个目标，也是 Rust 的特点（居然在官方上就能找到，不如说没有第一时间去官网看看是我太蠢了...）

* 高性能：零成本抽象，没有运行时开销；没有 GC（应该算在上一条的一部分）；容易和其他语言一起使用，特别是 C
* 可靠性：类型系统和所有权模型在编译期就能够解决一些内存安全和并发安全的问题
* 生产力：完备的文档；提供详细编译错误信息的编译器；包管理器 cargo；整合到 IDE 之内的自动补全工具等。当然，还有 Rust 丰富的库生态。

## Lecture 02: Memory Safety

首先给出了一些经典的 C 内存不安全的例子：

* 经典返回一个指向局部变量的指针（悬垂指针，Dangling Pointer）；
* 经典 double-free；
* 经典 malloc 之后忘记回收内存。

因此 Rust 引入了一些额外的约束来让我们更难以出现上面这些错误（重点是在编译期就能找出这些错误），但是在很多情况下仅使用 safe Rust 是不够的。

由于编译器的优化，在某些情况下 Rust 的性能优于 C。

结合之前看过的一些文章来理解 Rust 的所有权模型：有两个概念，分别叫做位置和值。所谓的位置也就是一块内存区域，它可以来自堆、栈或者全局数据段。值则指的是位置里面存放的内容。同时能够控制值和位置的就是类型，类型可以决定位置的大小，也能够决定如何理解值。

位置和值的二元状态一共有 5 种：即未初始化、有值、deleted、&、&mut 五种状态。

而所谓的所有权模型是说：每个变量独自控制（而非共享）一个有值的位置，称变量拥有这个有值的位置。变量至少要负责的是，当它离开作用域之后，需要将值和位置同时销毁。

> 一些非常平凡的情况，比如：
>
> * 位置是在栈上，那么函数返回之后这个位置就自动销毁了，不需要进行什么特别的处理；
> * 或者值的类型被标记为 Copy Trait，我们不需要对它进行任何特殊处理，只要销毁位置即可，可以随意让它作为无意义的内容留在那里。
>
> 一些相对不是很平凡的情况：
>
> * `Box<T>` 控制的是堆上一个有值的位置，所以在销毁它的时候首先需要回收堆内存，然后看看值的类型是不是需要在销毁值的时候做些什么。
> * 如果为值的类型实现了 `Drop` trait，那么在销毁值的时候确实有事情要做，但此时，就不能将这个类型同样标记为 `Copy`。里面的逻辑大概是，如果被标记为 `Copy` ，就基本证明在销毁值的时候什么都不用做。

Example1：初始化一个 String s，然后通过 let u = s 移走，最后输出 s。

> 它会编译错误，因为 String 里面是一个 `Vec<u8>`，并没有被标记为 Copy Trait。所以这里的赋值会取 move 语义，在按位复制之后，u 变为有值状态，而 s 变为 deleted 状态（此时位置还存在，所以可以考虑给它一个新的值），如果访问它会报出 moved value 错误。

Example2：初始化一个 String s，然后没有通过引用传参，最后输出 s。

> 它和上一个例子一个道理，在传参的时候也发生了 move 语义，值被移动到函数作用域的参数变量里面去了，原来的 s 进入 deleted 状态。

Example3：传参和赋值的时候是 u32 这种原生被标记为 Copy 的类型，所以没有问题。

但是只有所有权转移的话编程模型比较受限...

因此我们需要引用。确切地说，引用是一种类型，它是通过对另一个变量的借用而得到的。为了解决一些常见的内存安全问题，需要有以下的语义限制：

* 从非常广泛的一类读者写者问题中得到启发，变量在 & 状态下可以同时拥有多个不可变借用，而在 &mut 状态下只能拥有一个可变借用。变量在任意时刻都不能同时拥有不可变借用和可变借用。（这个主要针对并发安全，只有一个线程的情况下就没用了）
* 引用的生命周期不能超过它借用的变量的生命周期。

这被称为借用规则。

> 课件里面提到了一个细节，Rust 在编译期通过静态程序分析的方法计算每个变量的生命周期，得到的结果通常是 over-approximated 的。在静态程序分析中，比如说是要找出某种类型的错误，over-approximated 应该就是指找到的错误包含所有实际存在的错误，但也存在一些误判。不知道这里面的 over-approximated 又是指什么含义。

关于生命周期，这里没有很好说明的内容在于：

1. 在函数、结构体定义中的生命周期泛型参数；
2. 在某些时候智能指针可以代替引用，那么如何对于二者的使用进行取舍？

总之，Rust 在编译期保证了所有权模型和借用规则的检查，从而实现了某种程度上的内存安全。将运行期的开销转移到编译期是完全划算的，由于运行环境的复杂，很多情况下调试这件事情比较困难。事实上，安全和性能是很难兼得的，很多安全漏洞正是来源于极致的性能优化。Rust 的目标就是既要做到安全，也要保证高性能。

课件最后给出了很多关于 Rust 内存安全的参考资料，这个我们有空的时候回来看看。

## Lecture 03: Error Handling

本节课的前言提到这门课会有很多地方指出 C/C++ 遇到了什么问题，而 Rust 或者其他语言又是如何解决这些问题的，这也是我目前需要关注的重点。

里面提到在传参过程中转移所有权的时候，在 Rust 生成的汇编代码中传的是地址，这个说法听上去不太准确。 



空指针的发明者 Tony Hoare 提到空指针是他犯的一个很大的错误。尽管知道这并不安全，但是它实在是太容易实现了（太香了）。而空指针也确实在后面的四十年中导致了不计其数的漏洞和崩溃。在 CVE 上用 null pointer 作为关键词检索，能够找到[下面](https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=null+pointer)这些漏洞。

在 Rust 中，通过 `Option<T>` 来解决空指针问题。这个我们都已经非常熟悉了。

下面是错误处理。

在 C 里面，如果一个函数可能遇到错误，类型为 int 的返回值为 -1 代表错误（相反 0 则代表没有问题），类型为指针的返回值为 0 （空指针）代表错误（相反不是空指针则没有问题）。另外，有一个全局变量 errno，当调用者发现函数返回值有错误的时候，会到这个变量里面查看函数出现的错误编号来得知有错误的类型。课件里面给出了一个漏洞 CVE-2015-8812 来说明，但是我感觉这个漏洞更多是接口定义不一致导致的，而不是这套机制的问题？

> 我能想到的一个问题可能是 errno 应该需要是 thread-local 而不是 global 的，不然有可能产生并发冲突。

另一些语言则基于异常机制来完成错误处理，主要是 try-catch 块，在 C++/Java/Python 中都能够看到。课件中给出了它的一些缺陷：

* 难以确定错误发生的模式，因为*任何*函数在*任何*时间都可以不受限制的抛出*任何*异常；
* 代码难以维护。这是因为在定义函数接口的时候还需要加上这个函数可能抛出哪些异常，...
* 特别是进行一些手动内存管理的时候，我们难以确定语言运行时自带的堆栈展开等错误处理机制会对我们实现的逻辑有怎样的影响，而且语言的运行时很难修改。

> 这里我可以补充一点，就是软件异常控制流相比函数调用控制流并不自然，会引入一些额外的机制，更重要的是，还会带来运行时开销。

在 Rust 里面，错误一共分成两种：

* 如果系统发生了不可恢复的错误，则直接 `panic!`；
* 如果是可以恢复的错误，则函数会返回一个 `Result<T, E>`。它既可以表示函数成功返回，并包含返回值 `Result::Ok<T>`，也可以表明函数运行时出现了错误 `Result::Err<E>`。

对于 `Result` 而言，如果它是 `Result::Err`，使用 `unwrap` 或者 `expect` 都会直接 panic，不同的是 `expect` 可以附加一个额外的报错信息。

## Lecture 04: Object Oriented Rust

本节通过手动实现一个链表来复习之前讲过的所有权模型、借用检查、错误处理，此外还有 Rust 面向对象相关的知识。

> 在我的印象中，优雅的用 Rust 来实现链表看起来是一件很不容易的事情。

本节的链表存储的数据类型为 u32（不需要考虑泛型），需要实现常数时间复杂度的插入和删除，还需要维护它的 size 并能够打印里面的内容。

首先是链表节点的定义：

```rust
struct Node {
    value: u32,
    next: Box<Node>,
}
```

在链表中，总是需要一个指针指向下一个节点，往往这些节点都是通过 new/malloc 分配在堆上（但其实在以前写代码的时候也经常开一块全局区域，把所有的节点都保存在里面，甚至也支持简单的分配/回收。说起来，在内核中也能经常看到这样的实现方法）。这里面的 `Box<T>` 是一个智能指针，类似于 C++ 中的 `std::unique_ptr`，它控制堆上面的值（确切地说是有值的位置，但在这里为了说法方便简化为值）。当它离开作用域之后，会调用 `Drop::drop` 函数，里面会销毁堆里面的值并回收堆内存。因此，我们甚至不用任何 free ，就避免了一些比如忘记 free 导致的内存泄露，或者 double-free 这样的错误。

链表的最后一个节点的 next 域在 C/C++ 里面通常就是一个空指针，在 Rust 中我们需要引入 `Option<T>` 来解决这个问题。

```rust
struct Node {
    value: u32,
    next: Option<Box<Node>>,
}
```

> 这里有一个小问题：如果进行交换变成 `next: Box<Option<Node>>` 似乎也对，但是有哪些地方不太好呢？

然后链表作为另一个结构体，里面需要保存链表的头节点还有链表的长度。

```rust
pub struct LinkedList {
    head: Option<Box<Node>>,
    size: usize,
}
```

这里 `LinkedList` 被标记为 `pub` 而 `Node` 没有是因为我们只想对其他模块公开 `LinkedList`，而 `Node` 是作为 `LinkedList` 的实现细节，应该被隐藏。

在 `impl` 块里面，我们实现 `LinkedList` 的第一个方法：新建

```rust
impl Node {
    fn new(value: u32, next: Option<Box<Node>>) -> Node {
        Node {value: value, next: next}
    }
}
impl LinkedList {
    pub fn new() -> LinkedList {
        LinkedList {head: None, size: 0}
    }
}
```

下面是获取链表 size 的操作：

```rust
impl LinkedList {
    pub fn get_size(&self) -> usize { self.size }
}
```

这里面的 `self` 和 Python 一样是一个指向当前结构体自身的一个指针，不同的地方在于对于 `self` 的使用要带上所有权模型和借用检查，就像把一个结构体作为参数传给其他函数一样。这里，我们传入的参数是 `&self`，意味着这是一个不可变借用，则在函数体中我们不能修改结构体的任何一个字段（这并不是绝对的，后面还会有内部可变性这种东西）。此外，我们可以通过 `.` 运算符来访问结构体的字段。

那么，既然 `self` 是一个指针（类型 `&Self`），为什么可以用 `.` 来访问呢？事实上，我们确实可以像  C/C++ 一样通过 `(*self).size` 来获取 size ，但是没有必要。这是因为 Rust 会自动类型解引用直到类型匹配字段访问的行为。这里本来的类型是 `&Self`，而为了访问字段需要的类型是 `Self`，这只需要通过一次 `deref`，于是 Rust 就帮助我们完成了。事实上这也是 Rust 中的唯一一种隐式类型转换行为。我们可以手动实现 `Deref` Trait 来控制 `deref` 的行为。

> 需要特别小心，对于没有被标记为 Copy 的类型的引用进行解引用可能会转移所有权，因此可能无法通过编译。[这里](https://blog.kevinwmatthews.com/rust-ownership-and-dereferencing/)给出了一个具体的例子，但是是让另一个变量赋值为解引用之后的结果，这要求 Assignment 的 Source 拥有所有权，但是 Source 仅仅是一个 borrow，它并没有所有权，所以会报出错误 *cannot move out of borrowed content*。注：当我们提到所有权的时候，既有可能和位置有关系，还有可能和值有关系，这需要分不同情况讨论，但总之大概就是这么回事。
>
> 而课件这里面的例子没有尝试过，也许在 deref 的时候并没有发生所有权转移，因此可以通过编译。
>
> 这个问题由于时间关系我们就不深入探讨了，一些相关的内容：[rust reference: dereference operator](https://doc.rust-lang.org/stable/reference/expressions/operator-expr.html#the-dereference-operator),[rust reference: pointer](https://doc.rust-lang.org/stable/reference/types/pointer.html)
>
> 补充：[这里](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=8d1a2c32b154eff5036f62e0590d3bb1)有本讲完整的代码，尝试改成 `(*self).size` 确实也没问题，但这应该是 `&self` 特殊的情况，仔细想想确实没有发生 move 的必要，会被编译器优化掉。

后面的 `LinkedList::is_empty` 则是非常简单。

下面考虑加入一个节点，这是一种看上去没什么问题的实现：

```rust
pub fn push(&mut self, value: u32) {
    let new_node = Box::new(Node::new(value, self.head));
    self.head = Some(new_node);
    self.size += 1;
}
```

但是遗憾的是，它无法通过编译器的借用检查：

```rust
error[E0507]: cannot move out of borrowed content
  --> src/main.rs:49:50
   |
49 |         let new_node = Box::new(Node::new(value, self.head));
   |                                                  ^^^^ cannot move out of borrowed content
```

将 `self.head` 传给 `Node::new` 的时候，实际上本来 `self.head` 应该是一个 `&mut Option<Box<Node>>`，但是在传参的时候编译器发现需要的是 `Option<Box<Node>>`，于是自动解引用，因此在这个过程中实际发生了所有权转移。原因在于，这里的 `self` 是一个可变借用，它并没有实际的所有权。于是，又出现了 *cannot move out of borrowed content* 的错误。

这个时候就需要引入 `Option::take` 方法，它的函数原型是：

```rust
pub fn take(&mut self) -> Option<T>;
```

功能是将一个 `Option<T>` 内容拿出并返回，然后在自己里面只留下一个 None。

然后我们只需这样实现：

```rust
pub fn push(&mut self, value: u32) {
    let new_node = Box::new(Node::new(value, self.head.take()));
    self.head = Some(new_node);
    self.size += 1;
}
```

`self.head.take` 实际上在作用域里面生成了一个全新的变量保存 `self.head` 原来的值，然后再传给 `Node::new` 的时候完成所有权转移。

> 这里和之前关键的不同在于，`Option::take` 仅仅需要 `self.head` 的可变借用而不需要所有权。在实现 `Option::take` 的时候必然发生了类型为 `Node` 的所有权转移，而 `Node` 显然又没有被标记为 `Copy`，也许会遇到一些问题？看了 `Option::take` 的实现方法，它是直接使用 `mem::take` 来实现的，可以看成 move 语义的一种底层实现。
>
> 注意 `mem::take` 并不是 unsafe 的，而且适用于所有实现了 `Default` trait 的类型，因为无论类型是否被标记为 Copy，都不违背所有权模型。
>
> 这里展开有点太多了，我们来看接下来的内容吧。

然后是 pop 的实现：

```rust
pub fn pop(&mut self) -> Option<u32> {
  let node = self.head.take()?;
  self.head = node.next;
  self.size -= 1;
  Some(node.value)
}
```

为了绕过 borrow checker，我们还是需要像之前那样通过 `Option::take` 把 `self.head` 里面的东西拿出来，然后修改头节点并更新 size，然后将保存的值返回回来。注意，`self.head = node.next` 肯定发生了 move ，因为 `next` 域的类型 `Option<Box<Node>>` 并没有被标记为 `Copy` trait，而这次变量 `node` 可不是仅仅是一个引用，它是拥有所有权的，于是 move 成功，变量 `node.next` 应该也处于 deleted 状态，不过我们之后也不会再尝试访问它。而看后面我们还访问 `node.value`，可以说明 Rust 对于结构体中的每个字段都分别维护它的状态而不是一刀切，不然这个时候可能也会保存 use moved value 了。 

然后是打印链表中的元素：

```rust
pub fn display(&self) {
    let mut current: &Option<Box<Node>> = &self.head;
    let mut result = String::new();
    loop {
        match current {
            Some(node) => {
                result = format!("{} {}", result, node.value);
                current = &node.next;
            },
            None => break,
        }
    }
    println!("{}", result);
}
```

注意 `current` 的类型需要是引用，因为 `self.head` 在编译器自动 deref 之后是 `Option<Box<Node>>`，是不含引用的类型。这样的话 `let current = self.head` 的话又会出现 move，而目前的 `self` 仅仅是一个引用，是没有所有权的，这无法通过编译。而且也不符合我们的需求，在打印的时候我们并不想修改链表本身。

于是 `current` 的类型是 `&Option<Box<Node>>`。在通过 match 匹配的时候，`node` 应该是什么类型？应该是 `&Box<Node>`，不然的话又会把里面的 `Box<Node>` move 出来，没法通过编译。

> 这里并没有详细说明什么情况下会 move ，什么情况下则是按照引用匹配，我去找到了一些更详细的内容，有时间的话看一下：
>
> * [rust reference: patterns](https://doc.rust-lang.org/reference/patterns.html)
> * [rust blog: Mixing matching/mutation/moves in Rust](https://blog.rust-lang.org/2015/04/17/Enums-match-mutation-and-moves.html)

本节剩下的内容是为 `LinkedList` 实现了 `fmt::Display` 和 `Drop` 两个 trait，基本上只是对之前的内容进行了简单包装，在这里就不细看了，直接跳到下一节。

## Lecture 05: Traits and Generics

> 我自己学习的时候觉得非常愚蠢的地方就是分不清 Trait 和泛型。
>
> 现在还需要考虑一个问题，这如何体现了 Rust 的类型安全的？
>
> 有关类型安全的更多方面应该需要参考 [Rust 黑魔法](https://doc.rust-lang.org/nomicon/conversions.html) 的相关内容，我们在这里先不展开。

Trait 有些像 Java 里面的抽象接口 Interface，里面没有成员，当你为一个类型实现了 Trait 里面需求的所有抽象接口之后，就可能自动可以使用一些其他已经有默认实现的方法。（比如 `core::fmt::Write`）

课件里面提到的常用 Trait 如下（我自己也额外补充了一些）：

* 用来打印的 Display，以及跟它有点关系的 ToString
* 用来 move 或是直接复制的 Copy/Clone
* 迭代器相关的 Iterator/IntoIterator
* 用来比较的 Eq/PartialEq
* 用来自定义析构行为的 Drop（通常解决那些 Rust 默认无法做到的事情）
* 智能指针相关的 Deref/DerefMut
* 显式类型转换相关的 From/Into
* 闭包相关的 FnOnce/FnMut/Fn
* 异步相关的 Future
* 运算符重载，包括 `+,-,*,/,>,<,==,!=` 等。

有一些 Trait 可以直接通过 `#[derive(...)]` 来继承，并由编译器自动生成默认实现，但是如果是一个结构体，它至少也需要结构体内的每个字段都符合一些条件，让编译器有能力生成默认实现。

* 比较相关的 Trait：Eq/PartialEq/Ord/PartialOrd

* Clone/Copy：Copy 只是一个标记，课件中说的很好，它会将类型的 move 语义替换为 copy 语义。Clone 是 Copy 的 supertrait，也就是如果一个类型是 Copy 的，那么它必然是 Clone 的。Copy 的行为固定为按位复制，且是隐式进行的；而 Clone 的行为可以重载，而且只能手动触发。当我们 derive Clone 的时候，要求结构体中的每个字段都实现了 Clone trait，默认实现就是把所有的字段都 Clone 一下。

  > 比如，String 就是 Clone 但不是 Copy 的。

* 计算 Hash 值的 trait：Hash

* 让类型可以初始化为一个初始值的 Default

* 支持 `{:?}` 格式输出的 Debug

在我们为二维向量类型实现加法操作的时候引入了 Trait 中的关联类型：

```rust
impl Add for Point {
    type Output = Self; // an "associated type"
    fn add(self, other: Self) -> Self {
        Point::new(self.x + other.x, self.y + other.y)
    }
}
```

这里 `add` 的返回值可能写成 `Self::Output` 可能会更好。

在 Trait 之后，接下来就是泛型，比如之前已经见过的 `Vec<T>, Box<T>, Option<T>, Result<T, E>`。

关于泛型，我们需要认识到的重要一点就是它的多态是在编译期完成的，对于代码中所有实际使用到的类型，编译器会将泛型**实例化**，并生成一份对应的实现。实例化这个概念很重要，生命周期参数也是一种泛型。泛型可以出现在结构体、函数中。

Trait Bound 是将泛型和 Trait 结合起来的一种应用。我们可以对泛型加以限定，这样在为泛型编写方法的时候，我们知道它已经包含哪些 Trait 的特征。

比如有这两种写法：

```rust
impl<T: fmt::Display> fmt::Display for MyOption<T> { // more general!
     fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            MyOption::Sumthin(num) => write!(f, "Sumthin({})", num),
            MyOption::Nuthin => write!(f, "Nuthin :("),
        }
        
    }
}

// an example of "where" syntax
impl<T> fmt::Display for MatchingPair<T> where T: fmt::Display {
     fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "({}, {})", self.first, self.second)
    }
}
```

似乎有哪一个更加 general 的区别？我没去看视频不是很清楚。

如果是泛型函数，注意泛型参数声明的位置，以及可以通过 `+` 运算符取交集：

```rust
// An example of trait composition -- T must impl Display and PartialOrd
fn print_min<T: fmt::Display + PartialOrd>(x: T, y: T) {
    if x < y {
        println!("The minimum is {}", x);
    } else {
        println!("The minimum is {}", y)
    }
}
```

**泛型的开销**：零成本抽象！编译器会为不同类型生成多个版本的代码，对于一个具体的类型，会自动使用合适的版本。Rust 优秀的编译器使得这个开销并不大。这篇 [Rust 官方博客](https://blog.rust-lang.org/2015/05/11/traits.html)介绍了 Trait 的零成本抽象。当我们确实需要更进一步的抽象（动态分发）的时候，也就是 Trait Object 这种比较神奇的东西，才会确实的引入一部分运行时开销。

课件中给出了另一个用 Rust 写为 IoT 嵌入式设备开发的 OS：[Tock](https://www.tockos.org/)，并给出了其中使用 Trait 的两个例子 [1](https://github.com/tock/tock/blob/master/capsules/src/analog_sensor.rs), [2](https://github.com/tock/tock/blob/master/kernel/src/driver.rs)

下面是一些拓展阅读，我也列在下面：

1. [CS242 Notes on Traits](http://cs242.stanford.edu/f19/lectures/07-1-traits#partial-parametric-polymorphism)

   这个主要是非常深入的从编程语言理论的角度来看待 Rust 中的 Trait。CS242 本身就是一门 PL 课程。

2. [Common Rust Traits](https://stevedonovan.github.io/rustifications/2018/09/08/common-rust-traits.html)

   介绍了一些 Rust 中常见 Trait 的使用方法。

3. [Rust 官方文档中的 Trait 章节](https://doc.rust-lang.org/book/ch10-02-traits.html)

## Lecture 06: Smart Pointers

将值放在堆上并进行管理：`Box<T>`。

多共享引用：`Rc<T>` 允许同时存在堆上同一个值的多个不可变借用。如果我们只用 `Box<T>` 的话，由于它不是 Copy 的，这是做不到的。

>  于是问题是，`T` 只能存在于堆上吗？答案是肯定的。`Rc` 可以在 no_std 环境下的 `alloc::rc::Rc` 中找到，它存在的意义就是为了分配在堆上的类型 `T` 的值可以同时不可变借用给多个引用，每个引用都是一个 `Rc`，可以通过 `Rc::clone` 来新增一个。当最后一个 `Rc<T>` 离开作用域之后，堆上的值会被回收，意味着堆内存被回收，同时值会被销毁。
>
> 通常情况下我们无法在 `Rc<T>` 内拿到里面内容的可变引用。如果需要这样做的话，我们还需要一层内部可变性的 wrapper，比如 Cell 和 RefCell。[这里](https://doc.rust-lang.org/stable/core/cell/index.html#introducing-mutability-inside-of-something-immutable)给出了一个例子。在单线程环境下，共享引用可以使用 Rc，内部可变性可以使用 RefCell；而在多线程环境下，共享引用需要使用 Arc，内部可变性需要换成 RwLock 或者 Mutex。
>
> Rc 应该是在堆（所以堆是被 Rust 认为相对安全/合理来放置全局数据的地方，总比访问其他线程的栈要强）上分配了一块区域，里面有一个引用计数，还有被包裹在里面的值本身。Rc 是为单线程设计，引用计数的增减并不是原子的，这也导致它虽然开销比较小，但不是 `Send` 的，也就是不能安全的在线程之间转移所有权。这里的转移所有权的是有说法的，看看后面的课件看看能不能更容易理解一点吧。还有一个 `Sync` 是表示线程之间可以安全共享类型的不可变引用。总之，当我们想在多线程环境使用共享引用的时候，需要使用 `alloc::sync::Arc` 来替代 `alloc::rc::Rc`。
>
> 还有一个重要的部分就是 `Rc` 可以通过 `Rc::downgrade` 变成 `Weak`，它只保存不可变引用但不会累计引用计数。`Weak` 可以通过 `Weak::upgrade` 尝试升级为 `Rc`，但返回值是一个 `Option<Rc<T>>`，也就是里面包裹的堆上面的值已经被销毁之后则会返回 None，反之会成功返回 `Rc<T>`，引用计数也会增加。这个感觉挺神奇的，不知道是如何做到的。我们也可以直接使用 `Weak::as_ptr` 获取堆上值的 `*const T`，但是如果已经被回收了就会返回一个悬垂指针，它本身不是 unsafe 的，之后如何使用全看调用者。
>
> `Rc` 有一个方法是 `get_mut`，返回 `Option<&mut T>`，它是只有在没有任何其他 Rc 或 Weak 的时候才不会返回 None，因为只有这个时候是绝对安全的。另一个 unsafe 的方法是 `get_mut_unchecked` ，它则是不管怎样都直接返回堆上值的可变借用，完全不考虑潜在的并发冲突。在单核上这样做有意义吗？这个可能在内部可变性的地方进行探讨会更好一些。
>
> 如果两个对象互相拥有对方的 Rc，则它们都永远不会被回收，造成内存泄露。因此就需要将环打破。比如一颗树形结构中，父亲保存孩子的 Rc，而孩子保存父亲的 Weak。这个要分情况具体讨论，总之就是一个方向是 Rc，另一个方向是 Weak。
>
> 关于 Deref：`Rc<T>` 实现了 Deref Trait，可以将 `&Rc<T>` 自动隐式转换为 `&T`；而 `Weak<T>` 就没有实现这个 Trait，因为它并不清楚堆上的值是不是已经被销毁了。

课件中给出了一个例子，就是基于 Rc 实现一个可持久化链表。

内部可变：通过 `RefCell<T>`，我们可以只需要 `RefCell` 自身的共享引用就能够修改他里面包裹的内容。注意 `RefCell` 并不是分配在堆上的。

`RefCell` 会进行运行时的借用检查，因此会**带来运行时开销**。通过 `RefCell::borrow` 和 `RefCell::borrow_mut` 可以分别拿到 `Ref<'_, T>` 和 `RefMut<'_, T>`，它们分别实现了 `Deref` 和 `DerefMut`，可以当成 `&T` 和 `&mut T` 来用。但是它们在破坏借用规则的时候会直接 panic，比如 borrow 的时候发现已经有另一个可变借用了。相对更鲁棒的方法是使用 `try_borrow` 和 `try_borrow_mut`，它会返回一个 `Result` 而不会 panic。

一种多共享引用+内部可变的常见 pattern：`Rc<RefCell<T>>`。

此外，还有另外的两种 Cell，分别叫做 `Cell` 和 `UnsafeCell`，暂时还没有了解。

一些拓展阅读：

1. [Rust 官方文档的 Rc 章节](https://doc.rust-lang.org/book/ch15-04-rc.html)

2. [Rust 官方文档的 RefCell 章节](https://doc.rust-lang.org/book/ch15-05-interior-mutability.html)

3. [CS242 关于智能指针的讲义](http://cs242.stanford.edu/f19/lectures/07-2-smart-pointers)，会讲到 Box 和 Rc 是如何实现的。

   > CS242 利用 Rust 说明了 PL 的很多概念和设计，有时间（真的有吗？）可以去学习一下。

## Lecture 07: Multiprocessing Part1

本讲将讨论我们为何不在 Rust 编程中使用 fork/pipe/signal（如果是 C 编程的话那恐怕也没办法了 QAQ）

由于是基于标准库的，我们并不是特别关心，而且也就是 Rust 对上述 syscall 做的精巧封装，本质上都是一个东西。

## Lecture 08: Multiprocessing Part2 - Google Chrome

前面讲了一下我们为何不用 signal，这也许对了解 Linux/UNIX 有些好处，但是现在时间比较紧就略过了。

然后后面开始讲 Chrome 的工作原理啦！它的本质是一个多进程合作的任务。

进程之间可以通过信号和管道完成同步。而线程之间可以共享所属进程里面的资源（虚拟地址空间、文件描述符等），它们独自占有的是一个栈以及线程切换保存的寄存器。（等等好像跑题了？

当我们设计一款浏览器的时候需要考虑：多进程 v.s 多线程

* 速度：使用共享内存和轻量级的同步原语，这样速度才能比较快
* 内存占用：由于会同时有很多进程，内存占用会比较高
* 耗电/CPU 占用：使用线程替代进程会减少很多上下文切换开销（特指缓存失效问题）
* 开发便捷性：基于线程的话，任务之间通信会更加方便；*注意这也就意味着，多线程场景下的并发错误极难追踪*
* 安全性/稳定性：多进程提供了地址空间隔离，而多线程是共享的...

现代浏览器基本上就是一款操作系统！就好像每个网页都是一个应用程序，内核需要提供 API 给它们调用。API 也分为很多种：

* 存储 API；
* 并发 API；
* 硬件相关 API，包括与 MIDI/GPU 设备通信；

甚至它们还能执行汇编指令，甚至[在网页上跑 Win95](https://win95.ajf.me/)。

[Chromium 的一篇文章](https://www.chromium.org/developers/design-documents/multi-process-architecture)提到：2006 年左右的浏览器像是一个单用户、协作式多任务的操作系统，因此单个有恶意的网页就有可能让整个内核崩溃。现代操作系统将应用程序放在不同的进程中进行隔离，从而更加鲁棒。然而在浏览器中，会带来巨大影响的 bug 仍然非常多，且难以通过比较通用的工具/插件来解决。

> 我目前理解的浏览器安全：有点像是一个网页不能获取另一个网页的数据，也不能调用里面的 JS 代码？某种程度上和进程隔离有点像。

[Google 的一篇文章](https://developers.google.com/web/updates/2018/09/inside-browser-part1)介绍了现代浏览器的架构。而 Chrome 大概是浏览器自身一个进程，每个 Tab 一个渲染进程（直到近期为止都是这样），然后一些插件进程、GPU 进程和工具进程各自负责处理它们的任务。给每个 Tab 一个渲染进程的好处在于：如果一个页面未响应不会影响到其他的页面，直接将它关掉即可。另一个好处是带来了安全和沙盒。

多进程会带来更多的内存占用，尤其是内核部分的代码每个进程都需要一份拷贝。然而 Chrome 有一项很好的特性：它限制了每个进程能够使用的内存大小，在页面过多的时候，Chrome 也会将多个页面放在一个进程中。（这里的进程应该还是指 OS 进程而不是浏览器内核抽象出来的另外一种概念）这个特性不仅应用在页面的渲染进程中，对于 Chrome 自身的组件进程也是如此。在低端设备上 Chrome 可能会将自身的若干组件合成为一个进程来降低内存占用。

后面有更多页面隔离和沙盒相关的内容，和我想了解的内容关系不大，就先跳过了。

## Lecture 09: Intro to Multithreading

一个经典的并发漏洞：[Therac-25](https://en.wikipedia.org/wiki/Therac-25)

竞态条件是一个不局限于软件的概念，指的是一个系统的主要行为受到执行序列、时序、或者是其他不受控制的事件的影响，当这种行为不符合我们期望的时候就会触发 bug。

数据竞争则是指多个线程同时访问一个值，其中某个线程是写入操作。

这里面给出了两个例子来说明 Rust 相比 C 如何解决一些并发安全问题。

Rust 多线程的常用范式是 `std::thread::spawn` 用一个闭包作为参数（闭包捕获参数需要受到 Send 和 Sync 的限制，注意我们仍然主要思考最终的共存状态而不仅仅是 move 过程）。它会返回一个 `JoinHandle`。`JoinHandle::join` 会阻塞主线程直到对应的子线程结束，子线程 panic 不会影响到程序主体。

一段错误的 C 代码：

```c
for (size_t i = 0; i < kNumExtroverts; i++)
    pthread_create(&extroverts[i], NULL, recharge, &i);
```

这里是传了一个在主线程中会改变甚至被回收的临时变量的地址，明显是线程不安全的。

当我们尝试在 Rust 中这样做：

```rust
for i in 0..6 {
    threads.push(thread::spawn(|| {
        println!("Hello from printer {}!", NAMES[i]);
    }));
}
```

闭包会默认用不可变引用方式捕获变量 `i`。但是即使如此仍然有问题，Rust 会报错，原因是有可能主线程 `i` 已经离开作用域，子线程还在使用 `i` 的引用，造成悬垂指针。解决方法是强行在闭包前面加入 move 关键字让闭包使用移动语义进行捕获，由于 `i` 是一个 Copy 的类型，实际上它会被按位复制一份放到闭包里面。

另一段错误的 C 代码中，主线程将同一个变量的可变引用传给多个子线程作为参数。

# Lab

## week3

需要给 `LinkedList<T>` 实现 `IntoIterator` 和 `Iterator` 两个 Trait，触及知识盲区了，因此上来记录一下。

[这里](http://xion.io/post/code/rust-for-loop.html)给出了 Rust for-loop 的说明。

比如这段代码：

```rust
let v = vec!["1", "2", "3"];
for x in v {
    println!("{}", x);
}
```

这里的 for-loop 会把 v move 到循环里面。因此之后 v 就会被标记为 moved 状态了。

这是因为，for-loop 和赋值、传参的值语义一样，有可能发生 move 语义。同理，基于闭包的两种分别会/不会 move 的写法如下：

```rust
for_each(v, |x| println!("{}", x));
for_each_ref(&v, |x| println!("{}", x));
```

因此我们使用 ``for x in &v`` 就不会发生 move。

重要的是，``&`` 并不是 for-loop 的一部分，它只是让被迭代的类型从 ``Vec<T>`` 变成了 ``&Vec<T>``。这会导致迭代元素 `x` 的类型也从 `T` 变成了 `&T`。事实上在 Rust 中 `Vec<T>` 和 `&Vec<T>` 都是可迭代类型，通常被叫做迭代器。迭代器需要维护当前迭代到的元素并支持以下操作：

* 获取当前元素
* 迭代到下一个元素
* 当没有可用元素的时候告诉调用者

在 Rust 中 `Iterator` Trait 的 `next` 方法同时具有这些功能。

Rust 中使用 `IntoIterator::into_iter(self) -> Iterator` 来从一个类型创建 `Iterator`，注意它会将自身变成 moved 状态，之后只能使用生成的 Iterator 来访问。事实上 Rust 里面这种默认 move 的做法避免了 C++ 里面常见的 iterator invalidation 的隐患。重点就是：编译器不允许两个类 Iterator 同时存在。

事实上在 for-loop 里面调用了 `into_iter`，如 `for x in v` 可以改写成：

```rust
let mut iter = IntoIterator::into_iter(v);
loop {
    if let Some(x) = iter.next() {
        // body
    } else {
        break;
    }
}
```

因此 for-loop 只是这样一个语法糖而已。

如果我们将 `v` 换成 `&v`，相当于对 `&Vec<T>` 调用 `into_iter`，它的返回类型为 `Iterator<&T>`。同理，`&mut v` 返回类型为 `Iterator<&mut T>`。

当我们以如下方式使用迭代器和各种适配器的时候：

```rust
let doubled_odds: Vec<_> = numbers.iter()
    .filter(|&x| x % 2 != 0).map(|&x| x * 2).collect();
```

第一步首先是要获取迭代器。事实上 `iter()` 就是 `IntoIterator::into_iter(&numbers)` 的语法糖。他会生成一个 `Iterator<&T>` 的迭代器，因此适配器闭包里面的参数可以使用引用捕获。

也因此，我们实际上是要：

```rust
impl<T> IntoIterator for &LinkedList<T>;
```

这个会生成一个 `Iterator<&T>`。剩下的应该不用动了。

生成迭代器的常见方法：`iter()` 可以对 `&T` 进行迭代；`iter_mut()` 可以对 `&mut T` 进行迭代，`into_iter` 可以对 `T` 进行迭代。 

用全新的视角来阅读指导中给出的另一份[生命周期的文档](https://doc.rust-lang.org/1.9.0/book/lifetimes.html)。

Rust 的所有权模型是它零成本抽象的一个重要范例。生命周期的存在某种程度上解决悬垂指针或者 use-after-free 的隐患。

当我们在函数的参数/返回值中含有引用的时候需要显式或隐式（编译器帮助我们补全）带有生命周期泛型。比如：

```rust
fn bar<'a>(x: &'a i32);
```

在结构体中出现的生命周期泛型主要是保证作为字段的引用的生命周期比结构体自身要长（outlive），比如：

```rust
struct Foo<'a> {
    x: &'a i32,
}
```

生命周期自动补全的三条规则。