# 2. Bad Stack

## 2.1 Layout

* Using a defination of linked list from functional lang:

  ```haskell
  List a = Empty | Elem a (List a)
  ```

  We implement it directly by Enum in Rust:

  ```rust
  pub enum List {
      Empty,
      Elem(i32, List),
  }
  ```

  However, it does not compile:

  ```rust
  error[E0072]: recursive type `first::List` has infinite size
   --> src/first.rs:4:1
    |
  4 | pub enum List {
    | ^^^^^^^^^^^^^ recursive type has infinite size
  5 |     Empty,
  6 |     Elem(i32, List),
    |               ---- recursive without indirection
    |
    = help: insert indirection (e.g., a `Box`, `Rc`, or `&`) at some point to make `first::List` representable
  ```

  Compiler does not know the size of `List` at compile time.

* Now we reimplement it using `Box`:

  ```rust
  #[derive(Debug)]
  enum List<T> {
      Cons(T, Box<List<T>>),
      Nil,
  }
  ```

  And it worked!

  ```rust
  fn main() {
      let list: List<i32> = List::Cons(1, Box::new(List::Cons(2, Box::new(List::Nil))));
      println!("{:?}", list);
  }
  /// Output: Cons(1, Box(Cons(2, Box(Nil))))
  ```

  Rename its fields as a Rustacean(obviously they are the same thing):

  ```rust
  pub enum List {
      Empty,
      Elem(i32, Box<List>),
  }
  ```

* Consider a linked list having two elements, its memory layout will be:

  `[]` means on the stack while `()` means on the heap

  ```rust
  [ElemA, ptr] -> (ElemB, ptr) -> (Empty, *junk*)
  ```

  

