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