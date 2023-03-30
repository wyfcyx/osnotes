`sbi-rt`作用是能在内核里面绕过汇编使用sbi call，不过我们在教学中还是需要涉及汇编的。

根据SBI标准的话，`a7`寄存器应该保存拓展ID，而`a6`寄存器应该保存功能ID。

RustSBI原型化系统指的应该是[standalone](https://github.com/rustsbi/standalone)。这个研究一下的话...

---

教学OS所需的调用列表：

* BASE Extension(EID=0x10)中的各种支持
* Timer Extension(EID=0x54494D45)，FID=0的`set_timer`
* 如果需要多核支持：IPI Extension(EID=0x735049)，FID=0的`send_ipi`
* System Reset Extension(EID=0x53525354)，FID=0的`system_reset`，特别的参数`reset_type`需要传入`0x0`表示shutdown，而`reset_reason`可以用`0x0`表示no reason或者`0x1`表示system failure
* 串口相关，目前在已有拓展中不存在替代：console putchar和getchar，EID分别为0x01和0x02，FID=0x0

---

最好对于不同的qemu版本都提供支持，使用feature进行区分，比如`qemu-5-0`这种？

预期能够支持qemu5.x,6.x和7.x

如何更好地加入到项目中并提供CI/CD？

---

去看一下xv6的单文件实现看看哪些是我们的SBI中必要的内容。

* 修改`mpp`和`mepc`使得最后`mret`之后能够正确返回到S特权级的`rust_main`；
* 把所有的中断和异常代理到S模式（这一点感觉不好！）
* SIE全部设置为1，也很不好
* 进行PMP设置
* 调用一个比较复杂的`timerinit`函数；这里首先好像是做了本应是S态的一些逻辑，总之就是很没道理吧23333
* 读取`mhartid`到tp寄存器中
* 执行`mret`指令跳转到内核

---

希望能够加入一下设备树功能，以及可以通过feature配置是否将设备树传入内核以及是否对串口（或者包括串口在内的各种设备）进行初始化

---

将linker嵌入`build.rs`的做法值得研究一下。

---

我们能够借助rustsbi现有的哪些生态？一种比较理想的方法就是参考rustsbi-qemu和standalone，进行简化并只保留必要的东西，然后自己搞一个rustsbi-qemu-edu，之前也是这样设想的。但是之前似乎并没有深入研究可行性。

看了一下rustsbi的文档，感觉还不够，这个应该是给出了板子无关的一套rustsbi call标准通用的实现？那么研究一下现有的rustsbi-qemu，看看能够如何简化吧。

---

system reset相关：

首先是在QEMU层，在各种ISA上似乎都有reset的相关支持，比如在RV64架构下，只要选择带有sifive test device设备的board（比如virt），就可以使用到这种reset功能。做法大概是将一个值写入到QEMU指定的一个内存地址。在[sifive_test_device](https://docs.rs/sifive-test-device/latest/src/sifive_test_device/lib.rs.html#10)这个crate中可以看到是写入一个32位的值，低2字节表示正常退出=0x5555，失败=0x3333，重启=0x7777，然后如果是失败的话，高2字节可以表示一个errno。我看rustsbi-qemu的实现是传了一个-1的errno，结合这里的实现的话好像有点问题...

SBI call现在也有专门的reset调用了，有两个参数reset type和reason，在rustsbi-qemu里面可以调用sifive_test_device的接口，虽然感觉传参数有点不正确。

---

看代码的另一点感想是目前rustsbi和fast-trap的耦合有点紧...于是现在不太容易看得出执行流是如何从rustsbi切换到内核的，就非常麻烦...然后这个东西又跟SBI规范的HSM拓展有关系，最开始应该是使用的sbi_hart_start函数吧。这个可以设置内核入口以及进入之后的a0和a1参数寄存器。但是目前还没有找到具体什么地方进入的，可能需要到fast-trap里面看看了。

---

忽然发现，是不是我们遵从SBI1.0标准进行sbi call调用就能解决和RustSBI的兼容性问题了？因为看起来RustSBI理念是预计deprecated的接口一旦存在平替，就假定它们不会再被调用到了。无论如何这个是一定要做的，也就是我们的简化版sbi实现和内核都必须遵从1.0标准。我们先在内核中尝试一下看看是否能够解决问题。

但是RustSBI本身还存在和Qemu之间的兼容性问题，Qemu也会引入一些不向后兼容的修改，我觉得最有可能的就是MMIO地址吧，那么先去调研一下。至少从Qemu7.2.0来看（例如[这次commit](https://github.com/rustsbi/rustsbi-qemu/pull/45/commits/1699e349ac31dc7cd1511c1b119845a925e4ec2a)），看起来是因为Qemu的设备树描述文件发生变化导致原先的串口无法识别。如果我们依赖于某个固定的MMIO地址的话，很有可能后向兼容性相比dtb要更好。而且根据教学OS的实际需求，我们还希望有一些小trick，比如控制是否进行串口初始化（但是这样会导致RustSBI没有输出...），那么显然这个可以通过config来实现，最好不要在rustsbi-qemu里面弄？所以我们目前的想法还是弄一个rustsbi-qemu-edu。感觉确实有点伤脑筋...

又看了一眼，发现sbi spec已经更新到2.0-rc了，又新增了很多接口。



