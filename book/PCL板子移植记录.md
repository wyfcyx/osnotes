# PCL 板子移植记录

## 2020/8/11

* 终于到手了 PCL 这边做的 RISC-V  板子，听说是 RV64，支持 M/S/U 特权级，应该也支持 MMU，而且已经能在上面跑 Linux 辣！

* 我现在的任务是要把大 rCore 移植上去，能在上面跑一个 shell，不知道会不会比较顺利...

* 装了一个奇怪的串口驱动后（这导致目前只有 SmarTTY 能用，miniterm 需要另装驱动），终于能看到 Linux 已经跑起来了。之后大概要分析一下启动的流程。

  跟厉老师交流了一下，整体的启动流程是先执行 bootrom 上的代码将位于 SD 卡上的 bbl 和 kernel 载入到 RAM 上，而 bbl 和 kernel 目前是链接到一起的（类似 OpenSBI 的 FW_PAYLOAD 模式）。

  我们期望 bootrom + bbl 能帮我们搞定启动中尽可能多的事情。方便起见，bbl 大概可以不用动，kernel 的话，肯定不像 K210 那么多坑，应该只要把串口搞定就行了（考虑到现有的串口驱动可能跟板子上的串口不兼容）

* `/tetris` 是一个命令行俄罗斯方块，有点好玩...

* 等等，忽然想到文件系统需要读写 SD 卡，而 rCore 里面大概是没有 SD 卡驱动的...这个应该也需要搞一下。

* 先回顾一下 rCore 吧...重构之后是不是更加复杂了呢。

  在 wsl 上跑 Qemu 4.2 还需要装一下 libpixman-1-0。

  还是跟以前一个味，直接 `ls` 会找不到，需要 `/biscuit/ls` 才可以。 

  好像更正确的方法是使用 `busybox` 里面的封装的多种工具，比如 `/busybox ls`。

* 那我们现在把能在 PCL 板子上成功跑的 Linux 代码搞下来看一下，好像很大的样子（7GB 左右）。

  内网网速达到了 110MB/S，基本上将带宽跑满了。

* 很好奇，找到了 [Ariane 项目](https://github.com/openhwgroup/cva6)，里面提到自带支持的 FPGA 开发板好像就是我手里面拿到的 [Genesys2](https://reference.digilentinc.com/reference/programmable-logic/genesys-2/reference-manual)，然而[官网](https://store.digilentinc.com/genesys-2-kintex-7-fpga-development-board/)上据说已经卖没货了。也不知道 PCL 这边在 Ariane 基础上做了哪些改动，目前应该也不能看到样书。

* 移植大概分成这样几个阶段：

  1. 要能通过 OpenSBI 或 BBL（哪个方便选哪个）将控制转交给 rCore，并能通过串口输出字符
  2. 实现 SD 卡驱动（还涉及到 SPI）启用文件系统

* 这里面设备树疑似能够减小大量的工作量，我们先调研一下二者各是如何处理设备树的