https://doc.rust-lang.org/nightly/reference/subtyping.html

When `A:B` in Rust, we have `A` is a **subtype** of `B`, and `B` is a **supertype** of `A`.

This means that if a function receives  the supertype `B` as a argument, we can send it a variable of type `A` since `A` have all required methods of `B`.

However, if `A` is a subtype of `B`, what is the relationship between 2 derived types `&mut A` and `&mut B`? Is `&mut A` a subtype of `&mut B`?

Not exactly. What is interesting is that it can lead to a *meowing dog* problem. See the following code snippet:

```rust
trait Animal;
trait Cat: Animal {
    fn meow(&self);
}
trait Dog: Animal {
    fn bark(&self);
}
fn evil(a: &mut Animal) {
    // assuming that we can instantiate the trait
    a = Dog::new();
}
fn main() {
    let cat = Cat::new();
    evil(&mut cat);
    cat.meow();
}
```

After the function `evil` returns, the variable `cat` is of type `Dog`, and it no longer has the method `meow`! The Rust complier should not allow this code to compile, but how does it work?

To explain this, we should know what is a **type constructor**. A type constructor can compose generic types and create a new type. For example, `Vec` takes a generic type `T` as an argument and then generate a type `Vec<T>`. Similarly, the type constructor `&` take 2 generic types `'a` and `T` and generate a type `&'a T`.

Given that `F` is a type construction and `A` is a subtype of `B`, the **variance** is the relationship between `F<A>` and `F<B>`.

* covariant: `A: B` $\Rightarrow$ `F<A>: F<B>`
* contravariant: `A: B` $\Rightarrow$ `F<B>: F<A>`
* invariant: There is no relationship between `F<A>` and `F<B>`.

  Mention that if a type constructor takes multiple generic types, then the variance should be considered per generic type. For example, `&mut<'a, T>` is covariant over `'a` and invariant over `T`. Now we can go back to the code snippet, we know that `&mut Cat` is no longer a subtype of `&mut Animal` since `&mut<'a, T>` is invariant over `T`, thus the function `evil` cannot take a `&mut Cat` as input.

To be specific:

Table 1: mutable->invariant

|     type constructor     |   `'a'`   |    `T`    |
| :----------------------: | :-------: | :-------: |
|       `&'a mut T`        | covariant | invariant |
| `UnsafeCell<T>(Cell<T>)` |     -     | invariant |
|         `*mut T`         |     -     | invariant |

Table 2: immutable->covariant

| type constructor |   `'a`    |    `T`    |
| :--------------: | :-------: | :-------: |
|     `&'a T`      | covariant | covariant |
|     `Box<T>`     |     -     | covariant |
|     `Vec<T>`     |     -     | covariant |

Let's see another example:

```rust
fn evil<T>(dst: &mut T, src: T) {
    *dst = src;
}

fn main() {
    let mut a = "hello world!"; // &'static str
    {
        let s = String::from("goodbye world!");
        let b = s.as_str();
        evil(&mut a, b);
    }
    println!("{}", a);
}
```

If this compiles, in the last line we try to print a string that has been deallocated since the scope the string belongs to has exited. What happened? The exact types we send to the function `evil` are `&mut &'static str` and `&'b str`. Since `evil` is a generic function, the first thing we need to do is inferring the generic type `T`. We know that `&'a mut T` is invariant over type `T`, thus `T` has to be `&'static str` . After that, the type of the argument `src` is also `&'static str` while we provide it a `&'b str`. If it is acceptable, `&'b str` should be a subtype of `&'static str`. For the reason that `&'a str` is covariant over `'a`, we know that `'b` outlives `'static`, which is obviously impossible. 
