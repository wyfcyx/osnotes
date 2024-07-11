从[这里](https://docs.u-boot.org/en/latest/board/starfive/visionfive2.html)可以看到，u-Boot运行在s模式，也就是说它位于sbi后面的阶段，所以我们就可以舍弃掉了。等等，看起来使用的话会更加方便一点？不然的话要烧写镜像可就有点麻烦了。

启动流程：开机之后首先是BootROM，BootROM会读取RGPIO[1,0]的拨码决定后面的启动设备。看起来默认配置0,0下（这也是官方推荐的配置）走的是flash上面的SPL这一段小程序。顺便来看一下板子上16Mflash的布局：

* 0x0开头的0x80000，这512K为SPL；
* 0xF0000开头的0x10000，这64K为u-Boot环境变量；
* 0x100000开头的0x400000，这4M为OpenSBI+u-Boot的组合镜像fw_payload.img，其中OpenSBI为M模式，u-Boot为S模式，这个看起来也是板子出厂的时候就预置好的，但是后面也应该可以更新
* 0x600000后面都保留

从文档的意思来看，flash的MMIO起始地址为0。

回到SPL，fw_payload.img会被加载到DDR上，起始地址为0x4000_0000。（那么DDR的MMIO范围又是多少？）跳转到OpenSBI的0x4000_0000的入口。OpenSBI预处理之后跳转到u-Boot 0x4020_0000的入口。这里就已经是S模式了。那么kernel的物理起始地址就应该是0x4040_0000，因为fw_payload.img一共是4MiB。

接下来，看起来我们可以在u-Boot上loadx，通过串口将os.bin直接传输到vf2的DDR上，起始地址为0x4040_0000。然后跳转过去。好像还有一些细节要考虑，比如u-Boot怎么把dtb传给kernel？但是感觉跑到ch5是没有问题了。



跑通了，最大的坑在于USB2TTL连接时候，RX和TX要交叉，也就是板子上的RX GPIO要连到转换器上的TX，依次类推。然后转换器上的5v是不用连线的。另外，0x4040_0000是不行的，看起来u-Boot还需要占用更多的内存。因此我们设置为0x4800_0000是能够成功跑起来ch1的，其实肯定是不用给到128MB的，但是目前就先这样吧。进入u-boot之后，直接loadx 48000000，然后通过minicom的xmodem协议传输过去。然后go 48000000就行了。如果需要dtb的话，看起来可以使用bootm，好像比go功能要多上一点。

