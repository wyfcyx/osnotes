# core::pin

能够将数据固定在内存中它所在的位置的类型。

有的时候保证一些对象不会被移动是很有用的，这意味着他们在内存中的位置不会发生变化，某些情况下需要用到这个性质。最重要的应用当属自引用结构（即其中的某个字段是一个指向其他字段或者结构体本身的指针），当他们被移动的时候，其中的自引用指针将会指向错误的位置，从而导致未定义行为。

对于任何指针类型 `P`，`Pin<P>` 保证它指向的数据在内存中有着一个稳定的位置，也就是说这段数据不能被移动到其他位置上；在这段数据被 drop 之前，这块内存也不允许被重新分配。我们称指针 `P` 指向的那段数据被“固定”到内存中。

默认情况下，Rust 中的所有类型都是可移动的（movable）。Rust 允许所有的类型按值传递，对于常见的智能指针类型如 `Box<T>` 或 `&mut T` 则会发生所有权转移并将指针里面包裹的数据进行移动。你可以将 `Box<T>` 里面的数据拿出来，或者你也可以使用 `mem::swap`。`Pin<P>` 包裹一个指针类型，因此 `Pin<Box<T>>` 就像一个普通的 `Box<T>` 一样：当一个 `Pin<Box<T>>` 被回收的时候，它里面的内容也会被回收，同时对应的内存可以被重新分配。类似的，`Pin<&mut T>` 很像 `&mut T`。然而，一旦设置了 `Pin<P>`，你就不能再用之前的形如 `Box<T>` 或 `&mut T` 来访问被固定的数据，比如 `mem::swap` 就不能直接用了。

```rust
use std::pin::Pin;
fn swap_pins<T>(x: Pin<&mut T>, y: Pin<&mut T>) {
    // `mem::swap` 需要 `&mut T`，但是我们无法得到它
    // 这使我们很困扰，我们无法交换引用指向的数据了
    // 我们可以使用 `Pin::get_unchecked_mut`，但是它是 unsafe 的，因为：
    // 在 safe Rust 中我们不允许使用它把数据从 Pin 里面拿出来
}
```

值得强调的是 `Pin<P>` 的存在并没有改变对于编译器来说所有的类型都是可移动的事实。`mem::swap` 仍然对于任何类型 `T` 都可以调用。相反，通过使得像 `mem::swap` 这样需要 `&mut T` 类型的方法不可能被调用，`Pin<P>` 阻止了实际的值（也就是被包裹的指针指向的内容）被移动。

`Pin<P>` 可以被用来包裹任何指针类型，它也需要和 `Deref` 和 `DerefMut` 打交道。对于一个`P` 实现了 `Deref` trait 的 `Pin<P>`，它应该被看成一个指向类型为 `P::Target` 的一段被固定的数据的 `P` 风格指针。因此，`Pin<Box<T>>` 是一个指向被固定的 `T` 类型数据且具有对它的所有权的指针，而 `Pin<Rc<T>>` 是一个指向被固定的 `T` 类型数据的引用计数智能指针。出于正确性，`Pin<P>` 需要 `Deref` 和 `DerefMut` 的实现不会将它们的 `Self` 参数移动出去，并且仅在它们在一个被固定的指针上被调用的时候才会返回一个指向被固定的数据的指针。

## Unpin

很多类型在任何时候都可以自由地移动，即使它们被固定在内存中，因为它们并不需要被放在内存中固定的位置。这包括所有的基本类型（比如 `bool`，`i32` 以及引用）还有那些仅由它们组成的类型。这些不必被固定在内存中的类型会实现 `Unpin` trait，进而取消掉 `Pin<P>` 的影响。对于实现了 `Unpin` 的类型 `T`，`Pin<Box<T>>` 和 `Box<T>` 完全等价，`Pin<&mut T>` 和 `&mut T` 也是一样。

注意固定行为（Pinning）和 `Unpin` 只会影响指针类型 `P` 指向的类型 `P::Target`，而并不会影响被包裹在 `Pin` 里面的指针 `P` 类型自身。比如，无论 `Box<T>` 有没有实现 `Unpin` 都不会影响到 `Pin<Box<T>>` 的行为。

## Example: 自引用结构

```rust
use std::pin::Pin;
use std::marker::PhantomPinned;
use std::ptr::NonNull;

// 这是一个自引用结构，因为它的 slice 字段指向它自己的 data 字段。
// 我们不能用普通的引用来让编译器理解这种结构，因为它是违反借用规则的。
// 所以我们换成一个裸指针，当然它不能是空指针，因为我们知道它会指向它自己的 data 字段。
struct Unmovable {
    data: String,
    slice: NonNull<String>,
    _pin: PhantomPinned,
}

impl Unmovable {
    // 为了确保当此函数退出的时候 data 不会被 move
    // 我们将它放在堆上，从而在这个对象的生命周期之内它都会存在
    // 并且访问它的唯一方式便是通过一个指向它的指针
    fn new(data: String) -> Pin<Box<Self>> {
        let res = Unmovable {
            data,
			// we only create the pointer once the data is in place
            // otherwise it will have already moved before we even started
            slice: NonNull::dangling(),
            _pin: PhantomPinned,
        };
        let slice = NonNull::from(&boxed.data);
        // 我们知道它是安全的，因为改变其中一个字段并不会改变整个结构体在内存中的位置
        unsafe {
            let mut_ref: Pin<&mut Self> = Pin::as_mut(&mut boxed);
            Pin::get_unchecked_mut(mut_ref).slice = slice;
        }
        boxed
    }
}

let unmoved = Unmovable::new("hello".to_string());
// The pointer should point to the correct location,
// so long as the struct hasn't moved.
// Meanwhile, we are free to move the pointer around.
let mut still_unmoved = unmoved;
assert_eq!(still_unmoved.slice, NonNull::from(&still_unmoved.data));

// Since our type doesn't implement Unpin, this will fail to compile:
// let mut new_unmoved = Unmovable::new("world".to_string());
// std::mem::swap(&mut *still_unmoved, &mut *new_unmoved);
```





