# RustOS on Respberry Pi 4B

突然变颓...闲暇时间照着[这里](https://github.com/rust-embedded/rust-raspberrypi-OS-tutorials)学习一下。

## 00

项目的架构值得参考。比如同样是存储子系统的代码，被分为三种不同的层次：

1. `src/memory.rs` 或 `src/memory/*`：表示与指令集架构和具体硬件均无关的代码；
2. `src/_arch/__arch_name__/memory.rs`：表示只与指令集架构相关的代码；
3. `src/bsp/__board_name__/memory.rs`：表示只与开发板相关的代码。

然后，我们分别可以用 `crate::memory::*` 和 `crate::bsp::memory::*` 来引用相关的代码。

## 01

需要调整一下 Makefile 才能下载 Docker 镜像，就是在 `DOCKER_CMD` 最前面加上一个 sudo 来获取权限。

然后看上去是跑起来了，就是不知道输出是啥意思，而且只能通过 Ctrl+C 退出而不能通过 CtrlA+x。