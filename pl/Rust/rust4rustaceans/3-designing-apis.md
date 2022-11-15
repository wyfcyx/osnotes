# 3 Designing Interfaces

## Unsurprising

intuitive enough

### Naming

derived from common interfaces: for example, `iter, into_inner`

### Common Traits

users' expectation: `Debug, Clone, Sync, Send` and so on

coherence rule: users are not allowed to implement a foreign trait for a foreign type, instead, they should implement a wrapper

Therefore, you'd better implement all common traits for your type **even if you don't need them**

* Debug

* Send and Sync(also `Unpin`)

  when a type `T` does not correspond to any resources, it doesn't matter whether it's `Send` or `Sync`

  cannot `Mutex<T>` if `T` is not `Send`(otherwise 2 threads can `.lock().clone()` alternatively)

  if `T` isn't `Sync`, then we cannot `Arc<T>`(otherwise 2 threads can get `&T` at the same time) or make `T` static

* Clone and Default

* Comparison traits: `PartialEq, PartialOrd, Hash, Eq, Ord`

* `Serialize` and `Deserialize` from `serde`

* users prefer `Clone` rather than `Copy`

### Ergonomic Trait Implementations

extension: if `T: Trait`, provide supporting implementation for `&T, &mut T, Box<T>` as well

implement `IntoIterator` for `&T` and `&mut T` if `T` can be iterated over

### Wrapper Types

```rust
pub trait Deref {
    type Target: ?Sized;

    fn deref(&self) -> &Self::Target;
}
/// cheap ref-to-ref conversion
pub trait AsRef<T: ?Sized> {
    fn as_ref(&self) -> &T;
}
```

for most wrapper types: `From<InnerType>` and `Into<InnerType>`

`Borrow` is similar to `Deref` and `AsRef`, but it's especially suitable for the case that a type is essentially equivalent(in terms of `Hash, Eq, Ord`) to another one. For example, `Borrow` allows user to provide `&str` or `&String` to a `HashSet<String>`. 

> `Deref` conflict: if `T` can dereference to `U` and `T, U` both have method `f`, than `T t; t.f()` calls `T::f()` or `U::f()`?
>
> Solution: Make `f` static in `T`. Then we have `T::f(t)` and `t.f()`. 

## Flexible

API: (minimal) restrictions and (maximal) promises for backward compatibility

### Generic Arguments

one way of relaxing requirements, gradually adding trait bounds

but don't make every argument generic

dynamic dispatching instead of static dispatching to reduce the binary size at a cost at runtime: from `impl AsRef<T>` to `&dyn T`, mention that your user cannot eliminate the runtime overhead

currently, Rust's dynamic dispatch vtable is limited; user can always provides a trait object irrespective of the API

sometime, turning the API from concrete to generic types isn't backward compatible

### Object Safety

trait can be object-safe(user can `dyn Trait`) or object-unsafe(user cannot `dyn Trait`), we should prefer object-safe even  possibly with a slight cost

adjust the position of the generic parameters to try to keep the object-safety

consider whether we need to preserve object-safety(Do users want to use it as a trait object?)

object-safety can affect backward compatibility

### Borrow versus Owned

as efficient as possible

if lifetime is too painful to use for users, from references to owned data(Copy/Clone some lightweight data somewhere)

### Fallible and Blocking Destructors

explicit destructor function in addition to `Drop` implementation, "at least some errors can be seen"

problems & solutions...

## Obvious

### Documentation

1. list all the things users should do and possible effects(panic, error, UB and so on)
2. end-to-end usage examples at a crate/module level(more important than examples of specific types/methods)
3. organizing the documentation based on modules; take advantage of links; legacy APIs->`#[doc(hidden)]`
4. provide more external resources; `#[doc(cfg(...))], #[doc(alias="")]`, add indexes in the top-level doc

### Type System Guidance

how to assure that it's difficult for users to misuse your API

* semantic typing: using `enum` such as `Op::Add`

* using ZST to indicate the state of an instance of a type(`PhantomData<Stage>`, which is eliminated at runtime)

  state transition from `Type<Stage1>` to `Type<Stage2>`, different implementations

* `#[must_use]` annotation: generate a warning if user receives it but **not explicitly handle** it

## Constrained

### Type Modifications

make less types public

limitation on the user side: using `#[non_exhaustive]` to prohibit user from constructing instance using `Type {}`

### Trait Implementations

according to Rust's coherence rule, it's ok to implement traits for a new type, but it's possible dangerous to implement/remove traits for an existing type

an useful tool: sealed traits(tricky!)

### Hidden Contracts

1. re-exports: sometimes it's a problem to re-export types from external libraries
2. auto-traits: using Rust tests to check some auto traits consistently apply to your type
