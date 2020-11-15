# Rust embedded book 学习笔记

# 1. Introduction

[一篇介绍各种串口区别的回答](https://electronics.stackexchange.com/questions/37814/usart-uart-rs232-usb-spi-i2c-ttl-etc-what-are-all-of-these-and-how-do-th)

## [1.2 no_std](https://rust-embedded.github.io/book/intro/no-std.html)

详细介绍了一下 libcore 和 libstd 之间的区别，这个我在新版的 tutorial 里面也有提到。

## 1.3 Tooling

提到了使用 cargo-binutils 相比直接使用 gnu 工具链的好处在于，无论在任何 OS 上，只需一次安装就能在所有后端上使用，因为后端是基于 LLVM 的。这个工具的本质就是能够更好的使用 LLVM 提供的二进制工具。

调试基于 OpenOCD+GDB。[这里](https://rust-embedded.github.io/book/intro/tooling.html#openocd)对于 OpenOCD 的原理有比较详细的说明。

现在基本不想使用它的原因在于：首先是不稳定，其次是对于页表的支持不足。当然确实在嵌入式平台上一般没有这些问题。

## 1.4 Installation

直接跳过。

# 2. Getting Started

## 2.1 Qemu

通过 `#[entry]` 标记我们编写的入口 `main`，这个属性是由库 cortex-rt 提供的。

构建的话直接使用 `cargo build --target $TRIPLE`。

在使用 cargo-binutils 的时候，可以通过 `cargo readobj --bin app` 来自动找到项目中构建完成的可执行文件，如需要的话还会重新编译。通过 `cargo readobj` 可以读取 ELF 的 header 信息，而通过 `cargo size` 可以获取各个段的大小。

可以通过在 `.cargo/config` 中设置 runner 从而支持 `cargo run` 直接跑 qemu，比如：

```toml
[target.thumbv7m-none-eabi]
# uncomment this to make `cargo run` execute programs on QEMU
runner = "qemu-system-arm -cpu cortex-m3 -machine lm3s6965evb -nographic -semihosting-config enable=on,target=native -kernel"
```

在 Qemu 进行调试的时候，GDB 作为客户端，Qemu 则作为服务器。运行 Qemu 的时候需要加上参数：

* `-gdb tcp::3333` 告诉 Qemu 作为服务器监听本地的 3333 端口等待 gdb 连接；
* `-S` 告诉 Qemu 先停下来。