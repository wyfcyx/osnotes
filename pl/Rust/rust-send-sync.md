最近在写`async_modules`的demo的时候发现自己对于Rust里面的`Send`和`Sync`的理解还是不够深刻，因此再回过头来读一下相关的文档。

`Sync`意味着类型`T`的不可变引用`&T`可以安全的在线程间共享，其实更本质上是跨核共享（当这些线程在不同的核上并行跑的时候）。而`Send`意味着类型`T`可以安全的在线程间传递。“传递”这个字眼会让我们将大部分注意力放在“传递”也即数据拷贝这一过程。但其实我们更应该关心的拷贝结束后的终态，也即两个（二进制意义上）内容完全相同的类型`T`的实例分别在两个线程上**共存**是否安全。`T: Sync`等价于`&T: Send`，因为它们都在说同一件事情：即指向同一个`T`实例的两个`&T`可以在两个线程上安全共存。安全共存的含义是不存在任何数据竞争的风险。

> 有些时候我们可能只是单纯的将数据移动到另一个线程而不在原线程上保留一份副本。某些数据可能具有“线程亲和性”，即只有当它们在某个线程上时才有效。这样的数据也非`Send`。
>
> `Send`和`Sync`的区别：`Send`是安全的传递自身而`Sync`是安全的传递自身的不可变引用。

原生类型如`u8`或`u64`以及仅包含原生类型的复合类型都是`Sync`的。继承可变性（inherited mutability）的类型如`Box<T>`和`Vec<T>`也是`Sync`的，但前提是`T: Sync`。考虑我们有`&Vec<T>`，那么我们从中可以拿到`&T`。不可变类型`&T`是`Sync`的，反直觉的是`&mut T`也是`Sync`的。这是因为我们只需要`& &mut T`能在多线程上安全共存。而`&mut T`包上一层`&`之后实际上会变为只读的，也即等价于`&T`。 

提供内部可变性但线程不安全的类型不是`Sync`的，比如`Cell`和`RefCell`。另一个非`Sync`的类型是`Rc<T>`。在两个线程上，同一个`&Rc<T>`进行clone，会导致引用计数的统计产生数据竞争。相反，当需要线程安全的内部可变性时，可以使用原子类型如`AtomicBool`或者基于原子类型封装的同步原语`Mutex`或者`RwLock`等，这些类型都是`Sync`的。

但是有一个问题，`Mutex`等类型的`Sync/Send`其实某些情况下是对内层的`T`有要求的。比如：

```rust
impl<T: ?Sized + Send> Send for Mutex<T> {}
impl<T: ?Sized + Send> Sync for Mutex<T> {}
```

事实上我们期待的是对于任意类型`T`，`Mutex<T>`都应该是`Sync`的。那么为什么会对`T`有要求呢？（参考[reddit](https://www.reddit.com/r/rust/comments/cg96kj/help_understanding_send_with_mutex/)）特别地，为何`Mutex<Rc<T>>`就不是`Sync`呢（我们知道`Rc<T>`不是`Send`，再由上面的代码）。考虑我们在两个不同线程上有同个`&Mutex<Rc<T>>`，它们可以**在不相交的时间段**获取锁，并将内部的`Rc<T>`通过`clone`复制一份**移动到锁的外部**。在两个线程分别这样做之后，我们就在两个线程上有相同的`Rc<T>`，并显然会导致并发冲突。本质上讲，`Mutex<T>`的实现并不限制我们在拿到锁之后将锁保护的数据复制一份到锁的外部，这才要求`T`满足`Send`。

我们再来看一些其他的情况：

```rust
impl<T: ?Sized + Sync + Send> Sync for Arc<T> {}
impl<T: ?Sized + Sync + Send> Send for Arc<T> {}
impl<T: ?Sized + Send> Send for RwLock<T> {}
impl<T: ?Sized + Send + Sync> Sync for RwLock<T> {}
```

`Arc<T>`自身的引用计数是通过原子指令保护的。但是`Arc<T>`不能用来保护线程不安全（即非`Send/Sync`）的数据结构，因为我们可以在两个线程上同时拿到`&T`，因此需要`T`是`Sync`的。同时，两个线程也可以分别对`Arc`里面的内容进行clone（并非对`Arc`进行clone而更新引用计数）得到两个相同的副本，这则需要`T`是`Send`的。

`RwLock`先挖坑。