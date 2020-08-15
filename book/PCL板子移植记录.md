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

* 首先来看 rCore 代码，算是重新熟悉一下吧，希望目前里面没有 async...

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

## 2020/8/12

* 已经第二天了，好像还是没啥进度。

* 说回到昨天看的 rCore 设备树相关代码，在遍历之前应该就预先在 `DEVICE_TREE_REGISTRY` 里面插入了相应的初始化函数，然后在被遍历到的时候再去调用。

  确实如此，之前提到的以硬编码的方式初始化串口等设备，其实只不过是在 `DEVICE_TREE_REGISTRY` 里面插入了初始化函数而已。以串口为例，在调用 `serial::uart16550::driver_init` 时，做的事情仅仅是：

  ```rust
  DEVICE_TREE_REGISTRY.write().insert("ns16550a", init_dt);
  ```

  也就是在设备树中遍历找到设备 `ns16550a` 的时候会调用初始化函数 `init_dt`：

  ```rust
  pub fn init_dt(dt: &Node) {
      // 获取串口设备寄存器所在的 MMIO 基地址以及可能的偏移量
      let addr = dt.prop_usize("reg").unwrap();
      let shift = dt.prop_u32("reg-shift").unwrap_or(0) as usize;
      let base = phys_to_virt(addr);
      info!("Init uart16550 at {:#x}", base);
      // 使用 (addr, shift) 创建 SerialPort 实例的同时完成初始化
      let com = Arc::new(SerialPort::new(base, shift));
      let mut found = false;
      // 看起来 interrupts 保存的是 IRQ
      let irq_opt = dt.prop_u32("interrupts").ok().map(|irq| irq as usize);
      // 将 SerialPort 实例通过 Arc 保存到驱动总列表 DRIVERS 和串口驱动列表 SERIAL_DRIVERS
      DRIVERS.write().push(com.clone());
      SERIAL_DRIVERS.write().push(com.clone());
      // 尝试寻找串口设备的 interrupt-parent
      // 这里拿到的 intc 是个啥类型...?
      if let Ok(intc) = dt.prop_u32("interrupt-parent") {
          if let Some(irq) = irq_opt {
              if let Some(manager) = DEVICE_TREE_INTC.write().get_mut(&intc) {
                  manager.register_local_irq(irq, com.clone());
                  info!("registered uart16550 to intc");
                  found = true;
              }
          }
      }
      if !found {
          info!("registered uart16550 to root");
        IRQ_MANAGER.write().register_opt(irq_opt, com);
      }
  }
  ```

  不如来重新梳理一下 rCore 中的 I/O 子系统。

  首先，在 `driver/mod.rs` 给出了 `Driver` trait，需要实现的接口如下：

  ```rust
  pub trait Driver: Send + Sync {
      // if interrupt belongs to this driver, handle it and return true
      // return false otherwise
      // irq number is provided when available
      // driver should skip handling when irq number is mismatched
      fn try_handle_interrupt(&self, irq: Option<usize>) -> bool;
  
      // return the correspondent device type, see DeviceType
      fn device_type(&self) -> DeviceType;
  
      // get unique identifier for this device
      // should be different for each instance
      fn get_id(&self) -> String;
  }
  ```

  可见其主要的功能是用来处理 IRQ（注意可能需要一个 IRQ ID 也可能不需要），同时可以得到设备的类型、ID 等信息。

  可能存在的设备类型 `DeviceType` 如下：

  ```rust
  #[derive(Debug, Eq, PartialEq)]
  pub enum DeviceType {
      Net,
      Gpu,
      Input,
      Block,
      Rtc,
      Serial,
      Intc,
  }
  ```

  其中我们需要特别关注的是串口设备 `Serial`，块设备 `Block` 以及中断控制器 `Intc`。

  根据设备的类型不同，分别给设备的驱动程序继承了 `Driver` Trait，例如块设备驱动 `BlockDriver`、串口设备驱动 `SerialDriver`，它们都在能处理 IRQ 的基础上，增加了特定设备类型需要提供的基础接口，如 `BlockDriver` 需要提供 `read/write_block`；`SerialDriver` 需要提供 `read/write` 从串口输入一个字节或者向串口输出若干个字节。

  随后设置 `DRIVERS` 收集所有的驱动；`BLK_DRIVERS` 收集所有的块设备驱动；`SERIAL_DRIVERS` 收集所有的串口驱动；`IRQ_MANAGER` 保存一个全局的 IRQ 管理器实例。

  ```rust
  lazy_static! {
      // NOTE: RwLock only write when initializing drivers
      pub static ref DRIVERS: RwLock<Vec<Arc<dyn Driver>>> = RwLock::new(Vec::new());
      pub static ref BLK_DRIVERS: RwLock<Vec<Arc<dyn BlockDriver>>> = RwLock::new(Vec::new());
      pub static ref SERIAL_DRIVERS: RwLock<Vec<Arc<dyn SerialDriver>>> = RwLock::new(Vec::new());
      pub static ref IRQ_MANAGER: RwLock<irq::IrqManager> = RwLock::new(irq::IrqManager::new(true));
  }
  ```

  我们知道 `Driver` 的重要功能就是处理 IRQ，为了搞懂 IRQ 的处理原理我们还需要去看 `drivers/irq` 的相关代码。此时，我大概意识到，不摸清一个系统的整体构造，并深入到其中的很多细节，就根本搞不出来很好的抽象——

  刚刚提到的 IRQ 管理器 `IrqManager` 就是在 `drivers/irq/mod.rs` 中定义的：

  ```rust
  // Irq manager
  pub struct IrqManager {
      // is root manager?
      root: bool,
      // drivers that only respond to specific irq
      mapping: BTreeMap<usize, Vec<Arc<dyn Driver>>>,
      // drivers that respond to all irqs
      all: Vec<Arc<dyn Driver>>,
  }
  ```

  由于设置了 `root` 字段，看起来可能在设计上支持多级中断管理器，比如从总线到一个中断管理器再到下面的设备，最直观的例子可能就是多级 USB 了吧。不过目前的系统中只有一个 PLIC。

  `mapping` 字段保存了一个从 IRQID 到一个能够响应该 IRQ 的所有 `Driver` 的列表的映射，还有一个 `all` 保存对于所有 IRQ 都能响应的 `Driver` 列表，这个目前不知道作什么用。 

  `IrqManager` 的核心功能如下：

  ```rust
  // 将 (irq, driver) 二元组丢到 mapping 里面
  // 但是当 self.root 为 true 的时候，会调用 arch 的 enable_irq，也就是说认为每个平台的中断控制结构都是一颗有根树，其根设备由架构定义
  pub fn register_irq(&mut self, irq: usize, driver: Arc<dyn Driver>);
  
  // IrqManager 尝试处理一个 IRQ
  pub fn try_handle_interrupt(&self, irq_opt: Option<usize>) -> bool {
      if let Some(irq) = irq_opt {
          // 如果给出了 IRQ ID
          if let Some(e) = self.mapping.get(&irq) {
              // 如果在 mapping 查到了能够响应该 IRQ ID 的设备驱动列表
              for dri in e.iter() {
                  // 依次遍历列表中的每个设备尝试进行处理
                  if dri.try_handle_interrupt(Some(irq)) {
                      // 根据 Driver::try_handle_interrupt 接口定义
                      // 如果处理成功，则返回 true
                      return true;
                  }
              }
          }
      }
  
      // 上一步中没有找到找到能够处理的设备驱动，尝试在 all 里面寻找
      for dri in self.all.iter() {
          if dri.try_handle_interrupt(irq_opt) {
              return true;
          }
      }
      false
  }
  ```

  此外还有一个继承了 `Driver` trait 的 `IntcDriver` 表示中断控制器驱动，在能够 `try_handle_interrupt` 的同时还可以 `register_local_irq`。这个 `IntcDriver` 和 `IrqManager` 有关系，但不是一回事。

  顺便看看 PLIC 的搞法，首先在 `driver/irq/plic.rs` 搞了一个 PLIC 设备类型：

  ```rust
  pub struct Plic {
      base: usize,
      manager: Mutex<IrqManager>,
  }
  ```

  这里值得注意的是，`manager` 字段拷贝了一份 `IrqManager` 并用 `Mutex` 上了锁。

  `Plic` 首先应该是一个（中断）驱动：

  ```rust
  impl Driver for Plic {
      // 处理一个 IRQ，在 claim 和 complete 中间通过调用复制的 IrqManager 的方法来处理 IRQ
      fn try_handle_interrupt(&self, irq: Option<usize>) -> bool {
          // TODO: support more than 32 irqs
          let pending: u32 = read(self.base + 0x1000);
          if pending != 0 {
              let claim: u32 = read(self.base + 0x201004);
              let manager = self.manager.lock();
              let res = manager.try_handle_interrupt(Some(claim as usize));
              // complete
              write(self.base + 0x201004, claim);
              res
          } else {
              false
          }
      }
  
      fn device_type(&self) -> DeviceType {
          DeviceType::Intc
      }
  
      fn get_id(&self) -> String {
          format!("plic_{}", self.base)
      }
  }
  ```

  此外，需要实现 `IntcDriver` 把它变成一个中断控制器设备：

  ```rust
  impl IntcDriver for Plic {
      /// Register interrupt controller local irq
      // 这里也比较简单，就是打开了 PLIC 的相关 InterruptEnable 并将中断源的优先级设置为 7
      // 最后还要插入到 IrqManager 中的 mapping 里面去
      // 现在来看，Plic 中的 IrqManager 应该仅此一份，没有其他复制
      fn register_local_irq(&self, irq: usize, driver: Arc<dyn Driver>) {
          // enable irq for context 1
          write(self.base + 0x2080, 1 << irq);
          // set priority to 7
          write(self.base + irq * 4, 7);
          let mut manager = self.manager.lock();
          manager.register_irq(irq, driver);
      }
  }
  ```

  需要注意的是，这里只打开了 Interrupt Target1 的 IE，在普通的 SMP 架构下这应该对应于 Hart0 S Mode External Interrupt。所以如果是不支持中断代理的话，就会比较麻烦。

  现在我们终于可以尝试俯瞰 rCore 的整个 I/O 子系统了。

  整体的流程如下：

  1. 调用若干种设备的 `driver_init` 方法，其实都只是在将键值对插入到 `drivers/device_tree.rs` 中的 `DEVICE_TREE_REGISTRY` 中。这里的键指的是设备的 *compatible* 字符串，也算是代表设备的类型；而值是一个闭包（或称函数指针）`init_dt`，表示为设备编写的初始化函数。这些初始化函数不能现在就调用，因为需要一些从设备树 DTB 中得到的一些设备相关信息，最常用到的就是设备寄存器 MMIO 的起始地址。

  2. 调用 `device_tree::init(dtb)`，做的事情是验证 DTB 的合法性，解析 DTB 二进制数据，还原整颗设备树结构。随后遍历整颗设备树，对于每个设备，看它的 *compatible* 字符串是否出现在 `DEVICE_TREE_REGISTRY` 中，如果是的话则调用对应的设备初始化函数。值得一提的是，这里的实现通过给定不同标记遍历两次的方式来保证中断控制器设备一定先被初始化。

  3. 特化到 RISC-V 架构中，PLIC 设备总是被优先初始化为设备驱动实例 `Plic`，它实现了 `Driver` 和 `IntcDriver` 两个 trait，其中 `Driver` trait 需要实现的 `try_handle_interrupt` 函数在 `Plic` 这里用于实际处理 IRQ，其实只做了 claim 和 complete 两件事，根据 IRQ ID 找到相应地驱动进行处理或者没有 IRQ ID 也找到设备进行处理，都是 `Plic` 中的 `IrqManager` 类型的 `manager` 字段来负责的；而 `IntcDriver` 需要实现的 `register_local_irq` 函数在 `Plic` 中用于为其他外设注册 IRQ，做的事情是修改 PLIC 的 IE、Prioriry 寄存器并将键值对插入到中断管理器 `manager` 中。

  4. 以串口为例来看其他设备的初始化。和 PLIC 驱动类型 `Plic` 一样，串口驱动类型 `SerialPort` 也一样需要实现广义中断驱动 Trait `Driver` 以及设备特定的驱动（这里就是指串口驱动）接口 `SerialDriver`。 

     `SerialPort` 提供了一些跟设备寄存器打交道的基本手段：比如初始化函数 `init`（需要给定串口设备寄存器 MMIO 起始地址）；无阻塞单字节输出 `putchar`；阻塞式单字节输入 `getchar` 以及无阻塞单字节输入 `getchar_option`（函数如其名，返回一个 `Option`）。这些方法直接用来实现 `SerialDriver` 要求实现的 `read/write` 函数。而 `Driver` 要求实现的 `try_handle_interrupt` 则是在实际获取到字符之后调用 `trap::serial`，可能的作用是唤醒被阻塞的进程。

  5. 最后，我们来看真正遇到一个串口中断的时候整体的处理流程。中断明显在各平台处理方法都不同（因此需要对于 ARM/x86/RISC-V 架构都比较了解才能够将 HAL 抽象出去...），RISC-V 相关的中断处理放在 `arch/riscv/interrupt/mod.rs` 中。

     中断初始化并没有一个统一的 `interrupt::init` 函数，而是将时钟中断和外部中断分别进行初始化。时钟中断初始化只是打开了 `sie.stie` 并 `sbi::set_timer` 并没有什么不同；而外部中断初始化 `board::init_external_interrupt` 也只是打开了 `sie.seie`。现在还没有看到 Trap 是在哪里初始化的。

     后来才发现，目前的 rCore 将所有的 Trap 相关处理都封装到 [trapframe-rs](https://github.com/rcore-os/trapframe-rs) 中。当调用 `TrapFrame::init` 的时候，会将 `sscratch` 清零，并将 `stvec` 设置到 `trap_entry`。而 `trap_entry` 所做的事情是根据 `sscratch` 的值判断是从用户态还是内核态进入的 Trap，并跳转到不同的分支，最后保存上下文之后跳转到 `trap_handler` 函数。在这个库中，`trap_handler` 是以弱链接的形式定义的且没有实质内容，因此我们需要在 rCore 中提供自己的实现。之后发生的事情我们都很清楚：从 `trap_handler` 返回后就是恢复上下文并 `sret` 回到 Trap 之前的位置。

     所以只需要看需要我们在 rCore 中自己实现的 `trap_handler` 函数。由于收到一个 S 态外部中断，会分发到 `external` 函数，这个函数里面对于 U540 和 Qemu 的处理不同，Qemu 的话就会调用全局 `IRQ_MANAGER` 实例的 `try_handle_interrupt` 函数来处理 IRQ。

     > 全局 IRQ_MANAGER 实例和 Plic 里面那个 manager 都是 IrqManager，但是一个是将中断类型映射到相关的设备驱动实例（其实只有一种情况，就是将 S 态外部中断钦定 PLIC 驱动实例进行处理）；而另一个则限定在 S 态外部中断处理下面，将外部中断的 IRQ ID 映射到对应的设备驱动实例进行处理。

     所以，`IRQ_MANAGER` 将处理分发给 `Plic`，在 `Plic` 的 `try_handle_interrupt` 完成了 claim/complete 并在二者之间调用 `manager.try_handle_interrupt`，在给定了 IRQ ID 的情况下 `IrqManager` 容易从 `mapping` 找到串口驱动实例 `SerialPort`，并在它的 `try_handle_interrupt` 函数中调用 `trap::serial`，而这会进一步调用 `fs::TTY.push`，后续的内容我们不再深入下去。

* Liunx 在板子上的移植基于 [kernel 5.6.7 版本](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/snapshot/linux-55b2af1c23eb12663015998079992f79fdfa56c8.tar.gz)，同时在上面打了若干个 patch。理论上，把 rCore 移植到板子上应该比移植 Linux 要简单一点...

  现在要做的第一步就是：弄一个只输出一行 Hello world 的 kernel，通过 bbl 或 OpenSBI 能让它在串口上输出出来。这样算是一个不错的基础。

  首先是决定用 bbl 还是用 OpenSBI，我对于 OpenSBI 比较熟悉，但是 bbl 是可以跑。

  看一下生成能跑的镜像 `bbl_fpga.bin` 的流程：

  ```makefile
  # linux image
  buildroot_defconfig = configs/buildroot_defconfig
  linux_defconfig = configs/linux_defconfig
  busybox_defconfig = configs/busybox.config
  
  # benchmark for the cache subsystem
  cachetest:
  	cd ./cachetest/ && $(RISCV)/bin/riscv64-unknown-linux-gnu-gcc cachetest.c -o cachetest.elf
  	cp ./cachetest/cachetest.elf rootfs/
  	
  # cool command-line tetris
  rootfs/tetris:
  	cd ./vitetris/ && make clean && ./configure CC=riscv64-unknown-linux-gnu-gcc && make
  	cp ./vitetris/tetris $@
  
  vmlinux: $(buildroot_defconfig) $(linux_defconfig) $(busybox_defconfig) cachetest rootfs/tetris
  	mkdir -p build
  	make -C buildroot defconfig BR2_DEFCONFIG=../$(buildroot_defconfig)
  	make -C buildroot
  	cp buildroot/output/images/vmlinux build/vmlinux
  	cp build/vmlinux vmlinux
  	
  bbl_dtb_fpga:
  	dtc -I dts -O dtb riscv_fpga.dts -o riscv_fpga.dtb
  	cp riscv_fpga.dtb build/bbl_payload_dtb
  	
  bbl_fpga: vmlinux bbl_dtb_fpga
  	cd build && ../riscv-pk/configure --host=riscv64-unknown-elf CC=riscv64-unknown-linux-gnu-gcc OBJDUMP=riscv64-unknown-linux-gnu-objdump --enable-dmr-patch --with-dtb=riscv_fpga.dtb --with-payload=vmlinux --enable-logo --with-logo=../configs/logo.txt --enable-print-device-tree
  	make -C build
  	cp build/bbl bbl_fpga
  	
  bbl_fpga.bin: bbl_fpga
  	riscv64-unknown-elf-objcopy -S -O binary --change-addresses -0x80000000 $< $@
  
  ```

  这里面 `buildroot` 是一个能经过简单的配置就能在一个嵌入式设备上交叉编译 Linux 镜像的工具。

  首先是编译了两个用户程序 `cachetest` 和 `tetris` ，将二进制文件都放到 `rootfs` 目录下。

  随后生成 Linux 镜像 `vmlinux`，就是进入 `buildroot` 目录下面 `make defconfig` 然后再 `make`。这里面明显用上了之前的两个用户程序，在 `config/buildroot.defconfig` 确实执行了 `../rootfs`。

  接着，将 `riscv_fpga.dts` 编译成 DTB 格式（或称 FDT 格式，一回事）的 `riscv_fpga.dtb`。

  然后，是将 bbl、Linux 镜像、DTB 在 bbl 中打包到一起。在 bbl 项目中配置了一些编译选项，特别是提供了 DTB 和 Linux 镜像的地址，最终生成了可执行文件 `bbl_fpga`。

  最后一步则是将 elf 文件 `bbl_fpga` 变成一个纯二进制文件 `bbl_fpga.bin`。

## 2020/8/13

* 我觉得串口可能没有太大问题，工作量比较大的应该在 SD 卡这边。

* 我猜 bbl 应该都已经放在 RAM 上了，所以 SD 卡分区的事情应该是在 bootrom 上解析，并将位于合适位置的 `bbl_fpga.bin` 载入到 RAM 上，这样分析的话，应该就是把 OpenSBI 或者 bbl 跟 rCore 打包到一起来替换这个 `bbl_fpga.bin` 就好了。

  看了一下 bbl 的代码，感觉跟 OpenSBI 基本上是差不多的东西，还自带 DTB 解析模块，有点东西，加上它已经能跑了。真香警告。

  直接把 `riscv-pk` 项目单独拉出来，构建了一下，得到 `bbl`、`bbl.bin`。

  现在开始第一步，搞一个超简单的小项目，尝试在板子上输出 Hello world。

  另外有一个小问题，就是 bbl 怎么知道内核放在哪里，它好在初始化完毕的时候跳过去。

* 因为万恶的 wsl 识别不到 /dev/sd* 块设备，就没有办法用 dd 往 SD 卡上写固件了。然后，又因为感觉原先的双系统没必要，最近几天基本上很少用 Linux，但是它又吃了大量内存导致在 Win10 上虚拟机都开不起来。然后就折腾了一下把双系统恢复成单 Win10 了。然后又把 Win10 升级成专业版搞了个 Hyper-V，还折腾了各种 Linux 发行版。折腾到最后还是用了 VirtualBox + Ubuntu20.04，因为其他的都跑不起来。一个下午就这样过去了，我真的哭了...

  VirtualBox + Ubuntu20.04 倒是能检测到 /dev/sdb1（SD 卡的启动分区） 然后往上面 dd，但是两个环境不通就很难受了。啊浑身难受，先去个厕所冷静一下。

  那就等于一个下午全踩坑了。那就用之前一种奇怪的解决方案，用 Cygwin 就好了。dd 是可以用的，主要是不知道往哪块设备上面写。

* 尝试把 rCore-Qemu 镜像，板子上的 DTB 以及板子上能跑的 bbl 连到一起看看结果如何。

* 但是还是要知道 bbl 认为内核放在哪里。

  在 `encoding.h` 中找到 XLEN=64 的时候 `RISCV_PGLEVEL_BITS=9`，而 `RISCV_PGSHIFT` 一直为 12，因此在 `payload.S` 中应该按照 21 位对齐也即 $2\text{MiB}$。也就是说放在 $\mathtt{0x8020\_0000}$ 的地方。齐活，那 rCore 可能不用动了。（好像 Qemu 64 位也是一直放在这里，32 位放到 $\mathtt{0x8040\_0000}$，这是约定俗成的吗？）

  改动 rCore 代码，在输出 Hello world 之后死循环卡住。

* 手滑把之前的 ariane_fpga 删了，等解压的时候阅读一下 bbl 源码。

  一开始涉及到的都是汇编代码，在 `machine/mentry.S` 中。

  在 $\mathtt{0x8000\_0000}$ 第一条指令就是跳转到 `do_reset` 函数。`do_reset` 将所有通用寄存器和 `mscratch` 清零，然后将 `mtvec` 改为 `trap_vector` 作为 M 态 trap 的统一入口点，接着为每个 hart 设置不同的启动栈，然后清掉 bbl 自己的 `.bss` 段，然后将 `a0, a1` 分别设置为 hartid 和 DTB 所在的物理地址。最后对于 hart0，直接进入 `init_first_hart` 函数；对于其他 hart 则设置 `mip.msip`，并阻塞等待 hart0 发来的软中断。之后经过一些奇怪的处理之后进入 `init_other_hart` 函数。 

  `init_first_hart` 和 `init_other_hart` 函数均能在 `machine/minit.c` 中找到。在 `init_first_hart` 的开头就是在 DTB 中寻找可用的串口设备，当然，在这块板子上它最后肯定找到了

* 搞了一通之后发现 bbl 退出之后就没输出了...应该是 rCore 没有找到正确的串口驱动吧。这回尝试调用 sbi 的 `console_putchar` 试试看。又可以掏出之前的代码直接怼上去了。

  果然能正常在串口上输出啦！这我就不是很慌了。但是又出现了假换行的问题...

  现在的过程是先编译 kernel，然后再编译 bbl，然后把 bbl 镜像弄到 cygwin64 里面去写入 sd 卡，然后把 sd 卡插入板子，上电，按一下 reset，然后就要等待极其漫长的三分钟来等 bootrom 读 sd 卡上面的 bbl 镜像写入 RAM！这三分钟真的让反馈变得非常低效，好在我还能写文档来打发时间hahaha。

* 烧写时间还是没有得到改善。SmarTTY 很难用，于是换成 SecureCRT，感觉舒服多了。

## 2020/8/14

* 尝试一下正经的 rCore 吧，首先是要把输出替换成使用 `sbi::console_putchar` 来实现而不要自己弄一套驱动。

  从 `arch/riscv/io.rs` 来看，从串口驱动列表 `SERIAL_DRIVERS` 里面找到第一个驱动，其实际类型应该是 `SerialPort` 并实现了 `Driver` 和 `SerialDriver` 两个 trait，最后调用 `SerialDriver` 里面的 `write` 方法进行输出。

  可以先尝试一下这里不用自己找到的驱动而是用 bbl 提供的接口。改了一下之后正在烧写了。

  发现还是没有输出，但实际上在 `logging.rs` 中自己定义 `SimpleLogger` 实现了 `Log` 接口，里面的输出用到了 `crate::io::putfmt` 接口，难道我改成 `sbi` 的实现有误？

  先在进入 `rust_main` 之后调用 `sbi::console_putchar` 输出 `OK` 试一下。如果不是的话，可能是页表初始映射有点问题。 
  
  让我松了一口气的是，OK 没有问题，那说明 MMU 大概率也没问题。所以从 OK 到后面的 `info!` 输出有哪里炸了。
  
  发现 `println!` 在 `logging.rs` 中用 `arch::io::putfmt` 实现了，所以在 `logging::init` 之前需要用 `println!` 而不是 `info!`，不然当然没输出。
  
  改成了一堆 `println!` ，发现完全没输出，这就很诡异了。开始进入乱搞阶段。
  
  发现串口到 PC 的连接好像不太稳定。于是现在关掉板子之后拔掉 USB，然后重新开机之后再插上。但是太麻烦了就不这样做了。
  
  现在的问题好像是输出不了换行...?没有换行的话某些字符串能正常输出。但是明明昨天晚上的 tutorial 有换行也输出的很好啊。
  
  现在看起来 `info!` 完全不能用。把它删掉看一下。目前暂且不管它。
  
  发现在 `memory::init` 里面卡死了。（其实我觉得应该在内存初始化之后再初始化 Logger 的）
  
  猜想一下，`println!` 用不了，但 `print!` 没准能用。但现实是残酷的：`print!` 也不能用！我决定好好调查一下 `print!` 为啥用不了。不然后面非常麻烦。好像是因为 `format!` 是 `alloc` 提供了，所以没有内存分配器的话工作不了...然后我惊奇的发现 `format_args` 是 `core` 提供的，不用内存分配器。所以先把这个宏换掉试试吧。**正如我所想，现在果然有输出了！终于能用 info! 啦。这绝对是原版实现的漏洞之一。**
  
  很多 PC 端的串口中断对于换行的支持不好。我第一次了解到换行和回到行首是两个过程...在 securecrt8.7 上面按照[这里](https://blog.csdn.net/OHRadiance/article/details/48391703)说的改了一下，应该可以按照一般方法来处理换行了吧。这波是强迫症大胜利！
  
  然后看刚才的输出结果，给我弄出来一个 load address misaligned。有点恐怖，应该是内核重映射之后炸了。更具体一点，好像是初始化 timer 的时候炸了。
  
  现在又不知道在哪里 panic 了...怀疑是带参数的输出不能在初始化内核内存分配器之前调用。但是好像又不太对劲。
  
  怀疑刚才的 panic 的 USB 连接不稳定导致烧写到 sdcard 出了问题。现在 Hello RISC-V 能正常输出了。我再把它弄到内存分配器初始化之前来试试。验证了一下确实可以。目前死在初始化 timer：
  
  ```
  OK
  BOOT_HART here
  bss cleared
  [ INFO][0,-] init logging
  [ INFO][0,-] Hello RISCV! in hart 0, device tree @ 0xffffffffc0400000
  [ INFO][0,-] init trapframe
  [ INFO][0,-] frame allocator: init end
  [ INFO][0,-] mapping kernel linear mapping
  [ INFO][0,-] remap kernel end
  [ INFO][0,-] memory test passed
  [ INFO][0,-] init memory
  ../riscv-pk/machine/mtrap.c:23: machine mode: unhandlable trap 4 @ 0x0000000080003310
  Power off
  ```
  
  找到 $\mathtt{0x8000\_3310}$ 是在 `bbl/machine/emulation.c` 中的 `illegal_insn_trap` 函数中。我们可以先看一下为何会出现非法指令，以及非法指令是如何跳转进入该函数的。
  
  在 `bbl/machine/mentry.S` 中找到 `traptable`，明显是 vector 模式的 trap 跳转。
  
  在初始化时钟中断的途中加了很多 debug 信息来确定到底是哪条指令触发了非法指令异常。
  
  好像是进到 bbl 之后炸了？
  
  在 `mcall_trap` 加了一个 `printm` 输出一下 ecall ID，然后发现串口所有的字母输出都成乱码了，只能无奈改回去。
  
  好像把板子玩坏了，改回去之后还是乱码。感觉板子应该没坏，重启一下串口终端试试。果然重启之后就好了。但是我还是不知道哪里非法指令异常了 QAQ。
  
  尝试把修改 `timecmp` 那条语句删掉。但是还是报错...
  
  仔细比对一下，似乎是
  
  ```c
  extern uintptr_t illegal_insn_trap_table[];
  uintptr_t* pf = (void*)illegal_insn_trap_table + ((insn & 0x7c)<<1);
  emulation_func f = (emulation_func)(uintptr_t)*pf;
  ```
  
  这里解引用 `pf` 出的问题。
  
  尝试在 bbl 里面 trap 进 timer 处理之前加了一个 shutdown，发现并没用，说明还没进关键的那条 ecall 语句就死了。sad...最后发现还是 rdtime 炸了。我真的非常怀疑这 bbl 到底是个什么版本，怕不是也是 1.9.1 吧。那我斗争经验可太丰富了。
  
  好像这个 rdtime 在真板子上都跑不了...这算是个历史问题了？
  
  好在我有 dts 可以直接看到 clint MMIO 地址。
  
  芜湖起飞，这波直接是 $\mathtt{0x0200\_0000}$，跟之前一样。
  
  但是要搞一下页表映射...
  
  那只能通读一下原 rCore 的内存管理系统了...经典读代码。
  
* `arch/riscv/memory.rs` 里面调用了 `MemorySet::new` ，这里面的 `MemorySet` 是 `crate::memory` 里面的，也就是 `memory.rs` 里面。

  这里看到 `MemorySet` 其实用的是 `rcore_memory::memory_set::MemorySet<PageTableImpl>`。

  而 `PageTableImpl` 来自于 RISC-V 架构自己的实现 `arch/riscv/paging.rs`。

  而 `MemorySet::new` 终究转化为 `PageTableExt::new`：事实上要调用 `new_bare` 和 `map_kernel` 两个函数。

  至少有一个是从 $\mathtt{0xFFFF\_FFFF\_C000\_0000}$ 映射到 $\mathtt{0x8000\_0000}$（开头地址），空间大小为 $\mathtt{0x4000\_0000}$ 即 $1\text{GiB}$。这应该是第 511 项。

  那么第 509 项就是从 $\mathtt{0xFFFF\_FFFF\_4000\_0000}$ 映射到 $\mathtt{0x0000\_0000}$。

  所以已经映射完了，加上对应的偏移量就行了。

  **其实更具一般性的话，应该从 dtb 里面去解析 clint 地址。**

  好了，现在时钟中断初始化顺利完成了。接下来在解析块设备的时候爆炸了：

  ```
  [ INFO][0,-] timer: init end
  [ INFO][0,-] init timer
  [ INFO][0,-] init driver
  [ERROR][0,-] 
  
  panicked at 'Block device not found', src/fs/mod.rs:52:17
  === BEGIN rCore stack trace ===
  #00 PC: 0xFFFFFFFFC0201BDE FP: 0xFFFFFFFFC02A0CE0
  #01 PC: 0xFFFFFFFFC027C544 FP: 0xFFFFFFFFC02A0D40
  #02 PC: 0xFFFFFFFFC027B020 FP: 0xFFFFFFFFC02A0D70
  #03 PC: 0xFFFFFFFFC020646A FP: 0xFFFFFFFFC02A0DD0
  #04 PC: 0xFFFFFFFFC020275E FP: 0xFFFFFFFFC02A0EE0
  #05 PC: 0xFFFFFFFFC020308E FP: 0xFFFFFFFFC02A0F70
  === END rCore stack trace ===
  ```

  开一个新的 dot 来分析一下这个错误。

* 哦是因为没有设置 feature `link_user` 导致 rCore 尝试在 `BLK_DRIVER` 里面去找驱动，结果一个都没有。感觉设置一下 `link_user` 就能解决了？先跑起来，然后再替换掉块设备。（从 ramfs 替换到基于 sdcard）

  加上 `link_user` 发现卡死了 QAQ。那咋办啊...

  尝试减小一点用户镜像的容量吧。

  修改了 `user/rust` 里面不存在的 nightly 版本，折腾之后放弃了 ucore（找不到 rv32 的 musl-libc），编译之后发现每个 rust 用户程序都有 $2\text{MiB}$ 多！万恶的内核堆！

  **这个之后一定要改成 mmap 系统调用，搞得用户程序这么大实在不对劲！**

* 抽空研究了一下 sdcard 的驱动。K210 上大体上是按照一个块设备来访问的，基于一个 sector id 来进行读写。但是在 PCL 板子上的话好像还需要考虑到 GPT 的存在，是把用户镜像和内核镜像一起丢到第一个分区，还是把用户镜像单独扔到第二个分区呢？

  惨啊，没有找到裸机上的 GPT 驱动，不过当前[这个](https://docs.rs/gpt/1.0.0/gpt/)的话稍微改改应该还是能用的。

  可能是时候看一下 rCore 块设备驱动相关的代码了，尤其是用户镜像的载入方式。

  用户镜像的生成，主要是从这一条：

  ```makefile
  out_img := build/$(ARCH).img
  $(out_img): build rcore-fs-fuse
  	rcore-fs-fuse $@ $(out_dir) zip
  ```

  Qemu 里面使用的 `sfsimg` 还需要经过后续的包装：

  ```makefile
  $(out_qcow2): $(out_img)
  	@echo Generating sfsimg
  	@qemu-img convert -f raw $< -O qcow2 $@
  	@qemu-img resize $@ +1G
  sfsimg: $(out_qcow2)
  ```

  那么 kernel 又是在什么地方处理用户镜像的呢？

  根据教程第二版的经验，在 `fs/mod.rs` 里面找到链接用户镜像的位置，但是要打开某个选项：

  ```rust
  #[cfg(feature = "link_user")]
  global_asm!(concat!(
      r#"
  	.section .data.img
  	.global _user_img_start
  	.global _user_img_end
  _user_img_start:
      .incbin ""#,
      env!("USER_IMG"),
      r#""
  _user_img_end:
  "#
  ));
  ```

  这个 `.data.img` 段会被最终弄到 `.data` 段中。

* 明天继续。

