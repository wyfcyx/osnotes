# [18error-handling](https://doc.rust-lang.org/rust-by-example/error.html)

## 18.3 Result

`Result<T, E>` 是一个枚举类型，有 `Ok<T>` 和 `Err<E>` 两种可能。

和 `Option<T>` 一样可以 `unwrap` 。

如果 `main` 的返回值是个 `Result` 且实际并没有返回 `Ok` 的话能够看到错误。

### 18.3.1 map for Result

很多时候，我们需要确认函数可能返回的错误的类型。

然后像 `Option<T>` 一样，我们有比较方便的 `map` 和 `and_then` 可以使用。

`and_then` 的函数原型如下：

```rust
pub fn and_then<U, F: FnOnce(T) -> Result<U, E>>(self, op: F) -> Result<U, E>;
```

也就是说传给 `and_then` 的闭包是返回一个 `Result<U, E>`，而传给 `map` 的闭包的返回值类型是 `U`。

来看一个例子：

```rust
fn multiply(first_number_str: &str, second_number_str: &str) -> Result<i32, ParseIntError> {
    first_number_str.parse::<i32>().and_then(|first_number| {
        second_number_str.parse::<i32>().map(|second_number| first_number * second_number)
    })
}
```

确实能够融会贯通还需要一段时间。

### 18.3.2 aliases for Result

从模块化设计来说，最好一个子模块只会返回一种大的错误类型，当然里面可以再进行细分。

我们可以通过别名来简化错误类型的使用，如：

```rust
type AliasedResult<T> = Result<T, ParseIntError>;
```

### 18.3.3 Early Returns

这一节是通过 `match` 匹配来逐个尝试 early returns，之后会直接通过 ? 运算符。

### 18.3.4 ？

使用 ? 运算符，在遇到一个 `Err<E>` 的时候函数会直接返回。它的前身是 `try!`，现在也许还能使用。

## 18.4 Multiple Error Types

有的时候一个函数可能会返回多种不同的错误类型，我们需要加以区分。

### 18.4.1 Pulling Results out of Options

比如一个复合操作是先从 `Vec<&str>` 里面取出一个，然后 parse 成 `i32` 之后 double。显然 Vec 是空和 parse 失败是两种不同错误。

一种最基本的做法就是把错误层层包裹起来，比如

```rust
Option<Result<i32, ParseIntError>>
```

或者

```rust
Result<Option<i32>, ParseIntError>>
```

这种。

这里又介绍了一个新的组合子，`map_or`，它的函数原型是：

```rust
pub fn map_or<U, F: FnOnce(T) -> U>(self, default: U, f: U) -> U;
```

也就是 Result 里面有值就把值取出来然后做映射，否则返回 default。无论如何返回的都是 U 类型。

### 18.4.2 Defining an Error Type

可以定义一种新的错误类型，可能是一个 Enum，里面根据不同的错误原因带有相关的参数，并在 Display 的时候显示明确的错误信息。

组合子 `map_err` 是 Result 专属的，给它传入一个转换错误的闭包，就能转换错误类型。

### 18.4.3 Boxing Errors

可以将错误类型变成 `Box<dyn core::error::Error>`。为错误类型实现 Trait 即可，但是需要动态分发。

另外 `ok_or_else` 可以将 `Option<T>` 变成 `Result<T, E>`，需要传入闭包 `||->E`。

```rust
fn double_first(vec: Vec<&str>) -> Result<i32> {
    vec.first()
        .ok_or_else(|| EmptyVec.into()) // Converts to Box
        // Result<&str, Box<EmptyVec>>
        // argument of and_then: |&str|->Result<U,E>
        // 
        .and_then(|s| {
            s.parse::<i32>() // Result<i32, ParseIntError>
                .map_err(|e| e.into()) // Converts to Box
                // Result<i32, Box<ParseIntError>>
                .map(|i| 2 * i)
                // Result<i32, Box<ParseIntError>>
        })
}
```

