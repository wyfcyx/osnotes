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

*  首先来看 rCore 代码，算是重新熟悉一下吧，希望目前里面没有 async...

  `arch/riscv/boot/linker64.ld` 指定了内核的虚拟地址 $\mathtt{0xFFFF\_FFFF\_C020\_0000}$；

  同时通过设置 `_copy_user_start,_copy_user_end` 两个全局符号，如果将用户镜像直接链接到内核（使用 `.text.copy_user` 段）里面，那么是可以找到的。

  同时，注意到 `arch/riscv/board/u540` 里面专门为 U540 编写了 `linker.ld` 以及 `mod.rs`，`linker.ld` 里面的内容大致和 `linker64.ld` 相同，`mod.rs` 里面主要提供 PLIC IE 寄存器的设置、收到外部中断（也就是串口中断）的进行 claim/complete、以及设置串口的设备寄存器使能中断这三个功能。

  `arch/riscv/boot/entry64.asm` 里面是老生常谈的东西：为多个核设置不同的启动栈，进行内核初始映射，随后跳转到 `rust_main`。

  `rust_main` 在 `arch/riscv/mod.rs` 中，传入的两个参数分别是 hartid 以及 DTB 所在的物理地址。其中值得一提的是：在 `memory::init` 中，设置了 `sstatus.sum` 允许访问用户态虚存；初始化物理页帧分配器，这里用到了链接脚本提供的 `end` 符号来找到能够分配的物理地址区间，同时硬编码物理内存大小为 $128\text{MiB}$，并没有从 DTB 中获取；接着初始化内核堆，这部分代码写在 `src/memory.rs` 中；内核重映射 `remap_the_kernel` 函数在 `arch/riscv/memory.rs` 中，就是新建一个 `MemorySet` 然后 activate 它（设置 satp 并刷新 TLB），这里面的 `MemorySet` 在 `src/memory.rs` 中可以看到是 `rcore_memory::memory_set::MemorySet<PageTableImpl>`。好像之前的话也是单独把 `rcore_memory` 分离到另外一个库里面的。

  插一句，比较令人开心的是，在 rCore 的 master 上没有看到使用 Future 的痕迹，那么应该会比较轻松了。

  `PageTableImpl` 在 `arch/riscv/paging.rs` 中找到，可以发现其中的 `new_bare, map_kernel` 函数，也就是在内核重映射以及初始化用户进程的虚拟地址空间的时候用到的，也并没有对内核的各个段进行精细划分，而是通通搞一个 $1\text{GiB}$ 的大页过去。

  接着，对于非 U540 机器调用 `board::init(device_tree_vaddr)` 基于设备树进行设备初始化（然而rCore 支持的 RISC-V 机器除了 U540 就只剩 Virt 了）：

  ```rust
  pub fn init(dtb: usize) {
      serial::uart16550::driver_init();
      bus::virtio_mmio::driver_init();
      irq::plic::driver_init();
      rtc::rtc_goldfish::driver_init();
      device_tree::init(dtb);
  }
  ```

  它依次初始化了串口 `uart16550`、`virtio` 总线、中断控制器 `PLIC`、`RTC` 也就是 RealTimeClock，最后才是 `device_tree` 模块解析 DTB，但是感觉要用的设备都在之前用硬编码的方式初始化完了，这里起到什么作用呢？

  我们看到，在里面两次调用 `walk_dt_node` 对设备树进行两次遍历，找到所有 *Compatible* 的设备，第一次只处理所有含有 *interrupt-controller* 的设备，第二次只处理所有不含有 *interrupt-controller* 的设备。而所谓的处理是指...

  [这里](https://elinux.org/images/f/f9/Petazzoni-device-tree-dummies_0.pdf)找到一篇貌似还不错的设备树入门教程，先学习一个。
  
* 观察一下板子提供的设备树文件，其中：

  ```c
  // 串口
  uart@10000000 {
      compatible = "ns16750";
      reg = <0x0 0x10000000 0x0 0x1000>;
      clock-frequency = <50000000>;
      current-speed = <115200>;
      interrupt-parent = <&PLIC0>;
      interrupts = <1>;
      reg-shift = <2>; // regs are spaced on 32 bit boundary
      reg-io-width = <4>; // only 32-bit access are supported
  };
  ```
  
  其串口规范为 *ns16750*，找了一下也没有找到文档，估计要从给的 Linux 代码中移植。
  
  microSD 也是要经过 SPI 总线进行访问，所以要移植这两个驱动。
  
  