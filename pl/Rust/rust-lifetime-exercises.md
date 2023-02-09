参考链接1：[lifetime kata](https://tfpk.github.io/lifetimekata/index.html)

参考链接2：[lifetimes](https://github.com/mtomassoli/lifetimes)

Rust中的引用最大的意义在于避免数据拷贝，而且可以确保其引用的对象仍然存在。大多数现代语言通过引用计数来解决悬垂指针问题，C语言和汇编则直接将指针暴露给使用者。

# Kata ch1

这里有一个非常经典的例子，表明为什么编译器需要生命周期标注：

```rust
fn f(a: &i32, b: &i32) -> &i32 {
	if *a < *b { *a } else { *b }
}
fn g(a: &i32) -> &i32 {
    let m: i32 = 7;
    f(a, &m)
}
fn main() {
    let n = 10;
    println!("{}", g(n));
}
```

练习题

```rust
// 直接将引用原地返回，不存在悬垂指针
fn identity(a: &i32) -> &i32 {
    a
}

// 应该没问题
fn example_1() {
    let x = 4;
    let x_ref = identity(&x);
    assert_eq(*x_ref, 4);
}

// 这里可以知道悬垂指针了，但是不知道编译器是如何判定的
fn example_2() {
    let mut x_ref: Option<&i32> = None;
    {
        let x = 7;
        x_ref = Some(identity(&x));
    }
    assert_eq!(*x_ref.unwrap(), 7);
}
```

```rust
// 这里感觉是挺微妙的二选一，但无论如何返回值的lifetime需要是参数中两个lifetime的交集
fn option_or(opt: Option<&i32>, otherwise: &i32) -> &i32 {
    opt.unwrap_or(otherwise)
}

// 这里没问题
fn example_1() {
    let x = 8;
    let y = 10;
    let my_number = Some(&x);
    assert_eq!(&x, option_or(my_number, &y));
}

// 这里显然y被回收之后还再被借用
fn example_2() {
    let answer = {
        let y = 4;
        option_or(None, &y)
    };
    assert_eq!(answer, &4);
}

// 这个相比上一个就没问题
fn example_3() {
    let y = 4;
    let answer = {
        option_or(None, &y)
    };
    assert_eq!(answer, &4);
}

// 跟2一个道理，寄
fn example_4() {
    let y = 4;
    let answer = {
        let x = 7;
        option_or(Some(&x), &y)
    };
    assert_eq!(answer, &7);
}
```

# Kata ch2

如果参数和返回值生命周期标注相同，意味着什么？这里的说法是参数和返回值的合法区域必须完全相同。但我更倾向于这是在描述参数之间的一种联系，也就是说参数应该outlive返回值。

练习做完了。

# Kata ch3

生命周期自动标注规则，练习做完了。

# Kata ch4

在参数中存在可变引用的时候，即使不存在返回值也有可能需要生命周期标注。比如：

```rust
fn insert_value(my_vec: &mut Vec<&i32>, value: &i32) {
    my_vec.push(value);
}
```

这里面就有可能出现`my_vec`中插入不合法引用的情况。

多层引用的情况下，它们的生命周期标注可能不同，比如 `&'a mut Vec<&'b i32>`。

[q](https://tfpk.github.io/lifetimekata/chapter_4.html#do-we-even-need-two-lifetimes)
