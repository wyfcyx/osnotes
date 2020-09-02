# [easy_rust](https://github.com/Dhghomon/easy_rust)

* 这里不会做翻译，只是照着它来查缺补漏。

# Part 1

## Types

### Primitive types

```rust
assert_eq!(std::mem::size_of<char>, 4);

// .len() counts bytes
// .chars().count() counts chars
let a = "Hello!";
let b = "中国";
println!("{}", a.len()); // 6
println!("{}", a.chars().count()); // 6
println!("{}", b.len()); // 6
println!("{}", b.chars().count()); // 2
```

## Printing  'hello, world!'

* `->` is called "skinny arrow"

## Mutability (changing)

### Shadowing

* When you shadow a variable(maybe with different **type** and value), you don't *destroy* it but *block* it
* The origin variable can be seen after the lifetime of the shadow variable ends

## More about printing

* Using `r#` as a beginning and `#` as an end in order to make Rust ignore any escape characters inside the string.

* `b"<str>"|b'<char>'` return the bytes slice.

* Printing pattern `\u{<hex-len-4>}` gives an Unicode char. Example: `\u{D589}`。

* Other patterns: `{}` for Display, `{:?}` for Debug, `{:#?}` for pretty printing, `{:p}` for pointer

  `{:b}, {:x}, {:0}` for binary, hexadecimal, and octal respectively

  `{0}, {1}, {2}` refers to corresponding argument in the argument list

* It also supports printing very complex string such as:

  ```rust
  ---------TODAY'S NEWS---------
  |                            |
  SEOUL--------------------TOKYO
  ```

  By configuring variable name, padding character, min/max length and so on.