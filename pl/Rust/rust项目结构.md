Rust的项目层级是workspace->package->crate->module。

其中，每个package对应一个Cargo.toml，里面包含至多一个库crate和0个或多个二进制crate。每个crate都有一个crate root，对于库crate来说是`lib.rs`，对于二进制crate来说则可能是`main.rs`。

在Cargo.toml中，`[dev-dependencies]`用来声明在编译构建examples/tests/benchmarks时的依赖，在编译package本身的时候则不会用到这些依赖。这可以参考[Cargo Book](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html#development-dependencies)。

另外，在二进制和库crate共存的情况下，关于如何显式声明一个二进制crate所独有的依赖，可以参考[这个回答](https://stackoverflow.com/questions/35711044/how-can-i-specify-binary-only-dependencies)。但是看起来仍然是拆分成两个crates更加方便一些。丢到examples里面看起来也不错，执行的时候使用`cargo run --example fuse`就行了。

