研究一下`qemu-system-x86_64`上启用kvm情况下的多核启动。只能说目前优先搞定这个平台会比较省时间一点...

我们顺带将所有与x86有关的细节记录在这个文档里面吧。

## zCore完整启动流程

这需要我们看一下相关的Makefile。

```makefile
ifeq ($(LIBOS), 1)
build: kernel
run:
	cargo run $(build_args) -- $(ARGS)
test:
	cargo test $(build_args)
debug: build
	gdb --args $(kernel_elf) $(ARGS)
else
build: $(kernel_img)
run: build justrun
debug: build debugrun
endif

$(kernel_img): kernel bootloader
ifeq ($(ARCH), x86_64)
  ifeq ($(USER), 1)
	make -C ../zircon-user
  endif
	mkdir -p $(esp)/EFI/zCore $(esp)/EFI/Boot
	cp ../rboot/target/x86_64-unknown-uefi/release/rboot.efi $(esp)/EFI/Boot/BootX64.efi
	cp rboot.conf $(esp)/EFI/Boot/rboot.conf
	cp $(kernel_elf) $(esp)/EFI/zCore/zcore.elf
	cp $(user_img) $(esp)/EFI/zCore/
else ifeq ($(ARCH), riscv64)
	$(OBJCOPY) $(kernel_elf) --strip-all -O binary $@
endif

.PHONY: kernel
kernel:
	@echo Building zCore kernel
	SMP=$(SMP) cargo build $(build_args)
ifeq ($(ARCH), aarch64)
	@mkdir -p disk/EFI/Boot
	@cp ../target/aarch64/$(MODE)/zcore disk/os
endif

.PHONY: bootloader
bootloader:
ifeq ($(ARCH), x86_64)
	@cd ../rboot && make build
endif
```

其中需要留心x86_64平台上bootloader的构建。首先是`../rboot && make build`构建生成`rboot.efi`，应该是第一级bootloader的二进制。此外在zCore目录下还能找到一个`rboot.conf`，内容如下：

```
# The config file for rboot.
# Place me at \EFI\Boot\rboot.conf

# The address at which the kernel stack is placed.
# kernel_stack_address=0xFFFFFF8000000000

# The size of the kernel stack, given in number of 4KiB pages. Defaults to 512.
# kernel_stack_size=128

# The virtual address offset from which physical memory is mapped, as described in
# https://os.phil-opp.com/paging-implementation/#map-the-complete-physical-memory
physical_memory_offset=0xFFFF800000000000

# The path of kernel ELF
kernel_path=\EFI\zCore\zcore.elf

# The resolution of graphic output
resolution=800x600

initramfs=\EFI\zCore\fuchsia.zbi
# LOG=debug/info/error/warn/trace
# add ROOTPROC info  ? split CMD and ARG : ROOTPROC=/libc-test/src/functional/argv.exe?   OR ROOTPROC=/bin/busybox?sh
cmdline=LOG=warn:TERM=xterm-256color:console.shell=true:virtcon.disable=true
```

里面给出了一些后续启动阶段会用到的配置信息，至于具体哪里用到了后面再说。

在`/EFI/zCore/`目录下我们可以找到zCore的二进制`zcore.elf`以及文件系统镜像`$(user_img)`。`build`的过程主要就是生成`$(kernel_img)`，包括将一部分内容打包到`/EFI`目录下面。

当`make run`的时候，`build`的下一步是`justrun`，如下：

```Makefile
.PHONY: justrun
justrun: $(qemu_disk)
ifeq ($(ARCH), x86_64)
	$(sed) 's#initramfs=.*#initramfs=\\EFI\\zCore\\$(notdir $(user_img))#' $(esp)/EFI/Boot/rboot.conf
	$(sed) 's#cmdline=.*#cmdline=$(CMDLINE)#' $(esp)/EFI/Boot/rboot.conf
endif
ifeq ($(ARCH), aarch64)
	$(sed) 's#\"cmdline\":.*#\"cmdline\": \"$(CMDLINE)\",#' disk/EFI/Boot/Boot.json
endif
	$(qemu) $(qemu_opts)
```

这里的sed是Linux上自带的utils，是流式编辑器（Stream Editor）的缩写，功能是逐行操作一个给定的文件。这里的两行sed的意义是逐行对`rboot.conf`进行基于正则表达式的替换，`s`表示替换命令，`#`作为分隔符，三个`#`中间夹着的分别是替换前和替换后的内容，因此可以看出运行的时候会替换掉`initramfs`和`cmdline`的相关信息。如果我们不想用ramfs的话，可能这里需要做一点修改。

这之后，就已经启动qemu了，虽然`$(qemu_opts)`里面有一大段参数。找一找跟启动有关的参数（暂时不考虑fs）：

```makefile
esp := $(build_path)/esp
ovmf := ../rboot/OVMF.fd

ifeq ($(ARCH), x86_64)
  qemu_opts += \
		-machine q35 \
		-cpu Haswell,+smap,-check,-fsgsbase \
		-m 1G \
		-serial mon:stdio \
		-serial file:/tmp/serial.out \
		-drive format=raw,if=pflash,readonly=on,file=$(ovmf) \
		-drive format=raw,file=fat:rw:$(esp) \
		-nic none
```

这个[ovmf](https://github.com/tianocore/tianocore.github.io/wiki/How-to-run-OVMF)看上去是一个UEFI固件，据说是某个固件移植到qemu上的版本，专门用来启动qemu的。用法倒是没有什么问题，但是注意到rboot里面的ovmf 3年都没动过，难道是这里出的问题？我们首先尝试更新一下ovmf吧。这个文档里面还提到ovmf有可能不支持kvm...但无论如何只能试试了。[新版ovmf的下载链接](https://www.kraxel.org/repos/jenkins/edk2/)，然后我们先选择x64下面的pure-efi.fd（不带CODE/VARS）试试。

> 替换submodule的相关回答：[1](https://stackoverflow.com/questions/14404704/how-do-i-replace-a-git-submodule-with-another-repo),[2](https://stackoverflow.com/questions/913701/how-to-change-the-remote-repository-for-a-git-submodule)

折腾了一下换成最新版的OVMF还是没用...

总之，无论如何，OVMF的下一阶段应该就是rboot，zCore最开头的输出也是来自rboot。

不然我们先去找一下目前卡在zCore的什么位置？可以看到client已经成功向server上提交了请求，所以最根本的问题还是multiboot失败了，也即server core自始至终没有响应。那么server core卡在什么位置了呢？又或者是根本没有成功启动？

找一下zCore目前的实现中multiboot功能所在的位置。从目前的代码来看，最开始启动的时候应该是单核运行，然后这个核负责通过IPI来启动其他核。在kernel-hal中，bootstrap core会依次调用这两个方法：

```rust
fn primary_init_early(cfg: KernelConfig, handler: &'static impl KernelHandler) {
    info!("Primary CPU {} init early...", crate::cpu::cpu_id());
    KCONFIG.init_once_by(cfg);
    KHANDLER.init_once_by(handler);
    super::arch::primary_init_early();
}

fn primary_init() {
    info!("Primary CPU {} init...", crate::cpu::cpu_id());
    unsafe { trapframe::init() };
    super::arch::primary_init();
}
```

然后才会修改全局原子变量`STARTED`让其他core往下走。具体到x86_64平台上：

```rust
pub fn primary_init_early() {
    // init serial output first
    drivers::init_early().unwrap();
}

pub fn primary_init() {
    drivers::init().unwrap();

    let stack_fn = |pid: usize| -> usize {
        // split and reuse the current stack
        let mut stack: usize;
        unsafe { core::arch::asm!("mov {}, rsp", out(reg) stack) };
        stack -= 0x4000 * pid;
        stack
    };
    unsafe {
        // enable global page
        Cr4::update(|f| f.insert(Cr4Flags::PAGE_GLOBAL));
        // start multi-processors
        x86_smpboot::start_application_processors(
            || (crate::KCONFIG.ap_fn)(),
            stack_fn,
            phys_to_virt,
        );
    }
}
```

可以发现我们是在`primary_init`里面实现的Multiboot。有点想放弃治疗，剩下的明天弄吧。

在rboot之后，应该是将zCore elf加载到内存里面并跳转到`_start`函数（参考`zCore/src/platform/x86/entry.rs`），在这里面我们将rboot提供的`BootInfo`转化为`KernelConfig`，然后调用`main.rs`中的`primary_main`函数。注意`KernelConfig`里面设置了`main.rs`的`secondard_main`函数的地址。

`primary_main`中有这样一行（这里调用的是kernel-hal总体级函数，而上面代码段是低了一级的arch级函数）：

```rust
kernel_hal::primary_init_early(config, &handler::ZcoreKernelHandler);
```

这时其实是将`KernelConfig`写入到一个全局变量KCONFIG中。后面在arch级的`primary_init`中就用到了KCONFIG中的ap_fn，表示其他核启动之后，经过一段初始化汇编代码之后跳转到我们zCore的什么位置。

大致总结一下x86_smpboot的实现。大概就是通过主核的设置，副核应该能从(CS:IP=)0x6000的real mode开始运行，从这里开始会走[一段汇编代码](https://github.com/rcore-os/x86-smpboot/blob/master/src/boot_ap.S)，经过一系列初始化之后进入

等一下，先[关了ASLR](https://askubuntu.com/questions/318315/how-can-i-temporarily-disable-aslr-address-space-layout-randomization)看看kvm能不能跑，显然不行...发现KASLR和ASLR似乎不是一个东西，首先关掉KASLR（[1](https://askubuntu.com/questions/964540/gdb-qemu-cant-put-break-point-on-kernel-function-kernel-4-10-0-35),[2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/hibernation-disable-kaslr.html)），这样才能顺利在gdb里面打断点调试QEMU。第一，关掉KASLR之后还是不能正常跑；第二，还是不能直接打断点到zCore ELF里面。后来使用add-symbol-file代替掉普通file可以正常打断点了并continue了，又来了一个问题是在断点处不能正确停下来而是直接跑过去了。尝试了`_start`和`primary_main`都是如此...

另外发现一个问题，就是开头使用`thread 2`切换到副核之后直接`si`就可以开始跑，只不过此时地址是在`3ffXXXXX`不知道这是什么东西...

Intel官方文档vol3的8.4有多核启动相关信息，先扫一眼。x86_smpboot注释里面提到的则有可能是[这个文档](https://pdos.csail.mit.edu/6.828/2008/readings/ia32/MPspec.pdf)。

以上的尝试看起来都没什么用。于是问了一下rjgg和贾爷，贾爷告诉我可能是kvm需要x2apic但目前的smpboot硬编码使用xapic的问题。然后我就想能不能把smpboot里面的xapic换成x2apic。然后又和Lluis折腾了一下，发现启用kvm的情况下确实默认使用x2apic。但是如果在`-cpu`里面通过`-x2apic`关掉这个feature的话，原来的代码就直接能跑了！这是个好消息。

## zCore中断相关

