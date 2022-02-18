* 在 Rust Future 1.0 中，Rust 生成的 Future 枚举类会包含其他的子 Future。即 *size-inlining*。比如：

  ```rust
  enum RequestFuture {
    Initialized,
    FetchingId(IdRpcFuture),
    FetchingRow(GetRowFuture),
    WritingString(WriteStringFuture),
    Complete
  }
  ```

  对应于如下的 Combinator 代码：

  ```rust
  let future = id_rpc(&my_server).and_then(|id| {
      get_row(id)
  }).map(|row| {
      json::encode(row)
  }).and_then(|encoded| {
      write_string(my_socket, encoded)
  });
  ```

* Combinator/回调函数的痛点在于：与平常人们编写 Rust 程序的方式完全不同，且*不支持跨 yield 借用*。

  基于 async/await 重写上述 Combinator 代码：

  ```rust
  let id = id_rpc(&my_server).await;
  let row = get_row(id).await;
  let encoded = json::encode(row);
  write_string(my_socket, encoded).await;
  ```

## 零开销 async

* 最早，async 生成的 Future 大小会随着 await 的次数而指数级上升。这是因为，我们并没有对状态机树的每一层取一个 max，而是将整颗状态机树存下来，内存浪费可想而知。

  这并非 async/await 的设计缺陷，而是在早期实现它们的时候有意遗留下来的低效实现。这是一个相对固定的问题，但是需要在编译器层面做大量的优化。

* 早期的 async fn 是一个 generator。

  那么首先需要介绍 generator 是什么。

  generator 与 yield 关键字有关，如下面的代码：
  
  ```rust
  let mut gen = || {
      let xs = vec![1, 2, 3];
      let mut sum = 0;
      for x in xs {
          sum += x;
          yield sum;
      }
};
  ```

  我们需要对 generator 调用 resume 函数来让该闭包继续执行到一个 yield 并返回。其返回值分为两种：
  
  ```rust
  enum GeneratorState<Y, R> {
      Yielded(Y),
      Complete(R),
}
  ```

  于是 4 次 resume 的调用分别会返回 Y(1), Y(3), Y(6) 和 C。
  
  那么 generator 和 async fn 又有什么关系呢？我们知道 async fn 的关键在于可以通过 await 关键字挂起当前函数的执行等待另一个 Future 完成。而 generator 的 yield 恰好可以实现挂起当前函数执行的功能！
  
  实际上 .await 可以且确实是通过 yield 实现的。当我们优化 generator 的时候，也就是在优化 .await。
  
* generator 数据结构。

  一个更复杂的 generator:

  ```rust
  let xs = vec![1, 2, 3];
  let mut gen = || {
      let mut sum = 0;
      for x in xs.iter() {  // iter0
          sum += x;
          yield sum;  // Suspend0
      }
      for x in xs.iter().rev() {  // iter1
          sum -= x;
          yield sum;  // Suspend1
      }
  };
  ```

  