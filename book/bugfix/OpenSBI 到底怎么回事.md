## OpenSBI 到底怎么回事

* 之前对于 OpenSBI 这个项目不是很了解吧，现在不能直接拿到编译好的镜像，还是要看下怎么回事

* OpenSBI 的主要组件是一个平台无关的静态链接库 **libsbi.a**，它实现了 SBI 接口

  固件或者 bootloader 可以与它进行链接调用 SBI 接口

  它还定义了一个集成了平台固件提供的平台相关操作的接口

* 为了解释 **libsbi.a** 的使用方法，OpenSBI 还提供一些支持特定平台的例子，以平台相关静态链接库 **libplatsbi.a** 的形式给出。这个库是由 **libsbi.a** 继承平台上的特定操作得到的。对于所有支持的平台， OpenSBI 还提供若干由 **libplatsbi.a** 构建的运行时固件，他们可以作为 bootloader 使用。

## 构建 K210 上的 OpenSBI 镜像

1. 下载 [0.8 版本 OpenSBI](https://github.com/riscv/opensbi/archive/v0.8.tar.gz) 项目源代码

2. 配置命令行

   ```bash
   export CROSS_COMPILE=riscv64-unknown-elf-
   export PLATFORM_RISCV_XLEN=64
   ```

3. 构建 ``make PLATFORM=kendryte/k210``

4. 编译后的镜像文件可在 ``build/platform/kendryte/k210/firmware/fw_payload.bin`` 处找到

需要说明的是，可以构建[三种不同的固件](https://github.com/riscv/opensbi/blob/master/docs/firmware/fw.md)根据平台不同从中选择比较合适的：

* *FW\_DYNAMIC*：从运行时的上一阶段获取下一阶段的代码位置

* *FW\_JUMP*：从一个固定的位置获取启动下一阶段的代码（Qemu 一般使用这种方法）

* *FW\_PAYLOAD*：将启动后下一阶段的代码（通常是 bootloader 或 OS kernel ）也打包在该固件中

  相关的配置选项参见[这里](https://github.com/riscv/opensbi/blob/master/docs/firmware/fw_payload.md)

  还需要研究一下如何将得到的 rCore 打包进去

目前将得到的镜像烧写到 MaixDock，从串口看到了 OpenSBI 的输出如下：

```
[13:42:20:533] ␍␊
[13:42:20:533] OpenSBI v0.8␍␊
[13:42:20:533]    ____                    _____ ____ _____␍␊
[13:42:20:536]   / __ \                  / ____|  _ \_   _|␍␊
[13:42:20:549]  | |  | |_ __   ___ _ __ | (___ | |_) || |␍␊
[13:42:20:549]  | |  | | '_ \ / _ \ '_ \ \___ \|  _ < | |␍␊
[13:42:20:549]  | |__| | |_) |  __/ | | |____) | |_) || |_␍␊
[13:42:20:563]   \____/| .__/ \___|_| |_|_____/|____/_____|␍␊
[13:42:20:563]         | |␍␊
[13:42:20:563]         |_|␍␊
[13:42:20:563] ␍␊
[13:42:20:563] Platform Name       : Kendryte K210␍␊
[13:42:20:563] Platform Features   : timer␍␊
[13:42:20:577] Platform HART Count : 2␍␊
[13:42:20:577] Boot HART ID        : 0␍␊
[13:42:20:577] Boot HART ISA       : rv64imafdcsu␍␊
[13:42:20:577] BOOT HART Features  : none␍␊
[13:42:20:577] BOOT HART PMP Count : 0␍␊
[13:42:20:595] Firmware Base       : 0x80000000␍␊
[13:42:20:595] Firmware Size       : 72 KB␍␊
[13:42:20:595] Runtime SBI Version : 0.2␍␊
[13:42:20:595] ␍␊
[13:42:20:595] MIDELEG : 0x0000000000000222␍␊
[13:42:20:595] MEDELEG : 0x0000000000000109␍␊
```

