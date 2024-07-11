20240201

在没有文件系统之前，可以考虑在物理内存上开一个ring buffer，将trace写入到这个ring buffer中。

但是比较难搞的是，每条trace并非定长的（即使不是文本格式也很难搞成定长的，显然包含的信息量不同），就有可能涉及到动态内存分配。好的一点是，ch3可能直接开足够大的buffer不断append就行了，ch4开始有动态内存也很好搞了。

另外就是，如何将ring buffer的内容读取到host OS上。

参考[这篇blog](https://blog.reds.ch/?p=1379)，可以这样配置QEMU：

```
QEMU_ARGS := -machine virt,memory-backend=pc.ram \
			 -nographic \
			 -bios $(BOOTLOADER) \
			 -device loader,file=$(KERNEL_BIN),addr=$(KERNEL_ENTRY_PA) \
			 -m 128M \
			 -object memory-backend-file,id=pc.ram,size=128M,mem-path=pc.ram,share=on
```

其重点在`-machine`里面设置了`memory-backend`，和`memory-backend-file`对接上，同时打开`share=on`，这样虚拟RAM的内容就被记录到`pc.ram`上面了。猜测这样可能性能会比较低（但对于我们来说性能其实并不关键

当QEMU退出之后，就可以从`pc.ram`文件里面把trace捞下来，并放到perfetto网站上渲染了。

P.S. 这篇blog还介绍了如何把QEMU的RAM放到一个shmem上，这样其他进程在QEMU跑的时候也可以访问ring buffer了。如果是文件的话，QEMU和其他host进程同时只能有一个进程访问。但是，ring buffer就需要比较复杂的同步协议了。我觉得是在ch6引入文件系统之前都没有必要这样做。

---

ch6引入文件系统之后，可以直接定期或者手动把trace写入文件中，注意这里面也需要同步。比如捞trace的时候就不能新增trace了，而且由于我们文件系统过于垃圾，这个过程可能会很长。不过我们可以搞比较经典的两个buffer来回切换的机制。

另外，还有一个麻烦，就是之前的pid和tid最好不要重复使用了，我们好像没有什么手段判定两个相同pid的东西是不是一个进程...这个还挺麻烦的...

20240202

关于trace格式，一个可能有用的东西是：https://perfetto.dev/docs/instrumentation/tracing-sdk

[这里](https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU/preview?pli=1)（或者直接Google android trace event format）会告诉我们trace_marker的格式。

[这里](https://android.googlesource.com/kernel/common/+/bcmdhd-3.10/Documentation/trace/events.txt)可以在linux中查看trace event的格式。

```
sched_switch格式：prev_comm=%s prev_pid=%d prev_prio=%d prev_state=%s%s ==> next_comm=%s next_pid=%d next_prio=%d
这里就有个问题，为什么是pid而不是tid？
```

