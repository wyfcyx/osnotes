# Introduction

# 1 References

Rust 中的引用只有共享引用 `&` 和可变引用 `&mut`。它们的规则是：共享引用的生命周期不能超过被借用者，可变引用不能存在别名。但目前为止 Rust 并没有对什么叫做“存在别名”给出一个完善的定义，因此只能看看一些例子。

# 2 Aliasing

本节中讨论的别名的定义和 Rust 实际的定义相比更宽。同时只考虑单线程、无中断，也不考虑内存映射的外设。在这种情况下，定义别名就是指变量或指针指向了两块存在交集的内存。

比如如下函数：

```rust
fn compute(input: &u32, output: &mut u32) {
    if *input > 10 { *output = 1; }
    if *input > 5 { *output *= 2; }
}
```

编译器可能会将它优化成：

```rust
fn compute(input: &u32, output: &mut u32) {
    let cached_input = *input; // keep *input in a register
    if cached_input > 10 {
        *output = 2;  // x > 10 implies x > 5, so double and exit immediately
    } else if cached_input > 5 {
        *output *= 2;
    }
}
```

这几乎只能在 Rust 中完成，因为其他语言并不清楚两个参数是否存在别名现象。设想如果传入的两个参数分别是 `&x` 和 `&mut x`，这样不加检查直接优化显然是错误的。我们知道，在 Rust 中，`&mut` 不允许存在别名，在这里就是存在另一个引用指向一块相交的内存是不被允许的。

这就是别名分析如此重要的原因：它可以支持编译器进行很多优化。