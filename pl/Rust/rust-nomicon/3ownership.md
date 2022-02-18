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

这就是别名分析如此重要的原因：它可以支持编译器进行很多优化，比如：

* 在证明没有指针会访问保存值的内存位置的时候，将值保存在寄存器中；
* 如果证明一些内存在上次读入之后还没有被写入，将这样的读入消除；
* 如果证明一块内存在下次写入之前都不会被读入，消除这样的写入；
* 如果证明一些读写操作不互相依赖，则可以重排或者移动它们。

它们还可以用于更多强大的优化。

在上面的例子中，Rust 保证 `&mut u32` 不能有别名，使得对于 `*output` 的写入不会影响到 `*input`，从而可以将 `input` cache 下来来减少一次读入。

关于别名分析要记住的是写入操作是优化最主要容易出问题的地方。事实上，阻止我们将一个读入操作移动到程序任何地方的主要是它会和一个写入到相同内存位置的操作交换顺序。

如果我们将 `output` 的唯一一次写入移动到函数的末尾：

```rust
fn compute(input: &u32, output: &mut u32) {
    let mut temp = *output;
    if *input > 10 {
        temp = 1;
    }
    if *input > 5 {
        temp *= 2;
    }
    *output = temp;
}
```

则前面的部分很容易优化：因为只涉及到局部变量 `temp` 的写入可能和 `input` 冲突，而这是不可能的。于是我们可以轻易使用 cache 进行优化。所以最需要关心的仍然是写入。

当然，Rust 实际的别名检查需要考虑到更多方面：比如函数调用、裸指针和 UnsafeCell。

# 3 Lifetimes

Rust 通过生命周期来保证上面这些规则。生命周期是一个在执行期间某个引用必须持续合法的代码区域集合。它们可能相当复杂，因为它们与程序的执行路径相关。在这些执行路径中甚至可能有洞：我们可以在一个引用被再一次使用之前重新初始化它使得它不合法。包含引用或者装作是应用的类型也会被生命周期机制进行检查，所以 Rust 也能够避免它们变得不合法。

我们给出的大多数例子中生命周期都和作用域相关，因为它们都比较简单。后面也会给出一些相对复杂的例子。

在一个函数体中，Rust 一般情况下不允许你显式声明一个生命周期。这是因为在一个局部作用域中通常讨论生命周期是不必要的，Rust 有着所有的信息（包括一些匿名的作用域和临时变量）并能够最大限度的进行优化。

然而一旦跨越函数，就开始需要讨论生命周期了。生命周期是一个泛型参数，形如 `'a, 'static`。为了方便说明，我们显式给每个作用域一个生命周期标记。Rust 的语法糖消除了这些令人恼火的显式标注使得编程更加方便。

特别有意思的一个语法糖就是实际上每个 `let` 都会隐式引入一层作用域。大多数情况下它可能并不重要，然而一旦变量之间存在互相引用就不是如此了。比如我们将下面一段简单的代码：

```rust
let x = 0;
let y = &x;
let z = &y;
```

借用检查器总是试着最小化生命周期的延展长度，所以我们可能会显式标注成：

```rust
// NOTE: `'a: {` and `&'b x` is not valid syntax!
'a: {
    let x: i32 = 0;
    'b: {
        // lifetime used is 'b because that's good enough.
        let y: &'b i32 = &'b x;
        'c: {
            // ditto on 'c
            let z: &'c &'b i32 = &'c y;
        }
    }
}
```

实际上，当我们将引用传到外层作用域会导致 Rust 自动推导出一个更长的生命周期：

```rust
let x = 0;
let z;
let y = &x;
z = y;
```

```rust
'a: {
    let x: i32 = 0;
    'b: {
        let z: &'b i32;
        'c: {
            // Must use 'b here because this reference is
            // being passed to that scope.
            let y: &'b i32 = &'b x;
            z = y;
        }
    }
}

```

例子：引用outlive值

```rust
fn as_str(data: &u32) -> &str {
    let s = format!("{}", data);
    &s
}
```

编译器进行生命周期自动标注：

```rust
fn as_str<'a>(data: &'a u32) -> &'a str {
    'b: {
        let s = format!("{}", data);
        return &'a s;
    }
}
```

