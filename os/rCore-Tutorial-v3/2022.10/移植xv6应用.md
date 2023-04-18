看了一下，相比xv6主要缺失sbrk和一些文件系统相关的syscall。sbrk看起来在ch4的时候已经由bhy引入了，但是后面的章节好像还没有。文件系统相关的系统调用有：chdir/mkdir/mknod/fstat/stat/link/unlink。其中mknod是创建一个device文件；然后fstat和stat都是获取一个文件的stat信息，只不过fstat基于打开的fd，而stat基于路径；link应该是硬链接，而unlink是删除一个文件。

然而，需要注意的是在lab过程中还会多出一些syscall。就不去找之前的记录了，直接来看最新版本的lab吧。

# 2022版xv6 lab的一些有趣细节

## 1util

xv6 shell设置了一个快捷键，ctrl+p可以直接打印当前系统中的进程信息。

剩下的没什么好说的，简单的在xv6用户态做。

## 2 syscall

一个帮助熟悉如何通过gdb来调试内核，并引导学生了解syscall机制的问答环节。

添加一个trace syscall，参数为一个syscall编号的mask，表示跟踪mask中的syscall，即在syscall返回之前在屏幕上打印pid、syscall name和返回值。已经提供了一个trace应用程序可以提供mask并监控后面command的执行。

添加一个sysinfo syscall，参数为一个用户态的strcut sysinfo的指针，作用为收集当前的系统信息，目前只有两个字段：freemem以及nproc，表示进程个数。

挑战：trace的时候也打印syscall参数；sysinfo中计算进程的平均负载

## 3 pagetable

用户态getpid实现：在应用地址空间映射一个虚拟页，放在USYSCALL位置，放置一个usyscall数据结构，其中包含当前进程的pid。

页表打印：没什么意思，打出一大堆...

添加一个pgaccess syscall，报告应用地址空间中若干连续虚拟页具体有哪些页被访问过，即PTE中的Access标志位被硬件设置。以一个mask的形式返回到一个用户态buffer中。

挑战：使用大页（xv6中被称为super-pages）减少页的数量；让合法应用地址空间不是从0开始；类似pgaccess统计dirty的页，使用PTE_D标志位

## 4 trap

通过反汇编熟悉rv calling convention。

实现backtrace：本身挺基础的。有趣的是可以通过`addr2line -e <elf>`，然后在里面输出一串（每行一个ra地址），然后Ctrl+D，来将地址转换为代码行。

添加一个`sigalarm(n, handler)` syscall，意味着进程每n个时间片暂停当前执行，调用一次handler函数，handler返回之后再恢复之前的执行。调用`sigalarm(0, 0)`则会停止上述行为。

挑战：不借助addr2line，在backtrace中打印函数名和行号

## 5 copy-on-write

挑战：统计实现COW之后，减少了多少数据拷贝和页分配，考虑如何进一步优化。

## 6 multithreading

uthread：实现green thread机制，看上去应该是N:1模型。

基于pthread练习缩小pthread mutex锁粒度。

基于pthread cond实现一个barrier。

挑战：实现多个uthread能够在多核上并行执行，此前是做不到的，假如一个uthread进入syscall，其他uthread也没法继续执行。除了1:1线程模型的传统方法之外，还提到了一种scheduler activations的方法，其实也就是N:M混合线程模型。

## 7 networking

在xv6中实现E1000网卡驱动，QEMU负责模拟网卡设备以及它连接到的模拟局域网（LAN）。在模拟LAN中，guest xv6的IP地址为10.0.2.15，而host的IP地址则为10.0.2.2。当xv6通过E1000网卡向host IP发包，qemu会将这个包转发给host上对应端口的某个应用。这需要启用QEMU的[用户态网络栈](https://wiki.qemu.org/Documentation/Networking#User_Networking_.28SLIRP.29)。Makefile配置QEMU将收到和发出的所有包记录到一个packets.pcap文件中，然后通过`tcpdump -XXnr packets.pcap`可以展示这些包。

相关的代码有：ethernet E1000网卡驱动、从PCI总线上寻找E1000网卡的代码以及IP/UDP/ARP网络协议。

在`e1000_init`中，我们将E1000配置为通过DMA（也就是在RAM中有收发缓冲区，使用`struct mbuf`描述）与xv6通信。由于收包的速度可能大于处理包的速度，所以我们需要同时缓存多个包。我们通过描述符`struct rx_desc`来描述一个收发缓冲区，显然其中应该包含缓冲区的起始地址。另外还需要在内存中分配两个描述符的ring buffer，收和发端的size分别为`RX_RING_SIZE`以及`TX_RING_SIZE`。

`net.c`中的网络协议栈调用`e1000_transmit`来发包，参数为一个`mbuf`。这需要将一个描述符放到TX ring中。注意当E1000将这个包发送出去之后，还需要将mbuf对应的缓冲区回收。当E1000从ethernet收到一个包之后，它会将包放到RX ring的下一个描述符指向的缓冲区中。如果启用了E1000中断，当收到包的时候如果一个E1000中断未处于pending状态，E1000会要求PLIC向CPU发送一个中断。我们的`e1000_recv`应该会在中断处理中被调用，此时需要将RX ring中的所有包通过`net_rx`发送到网络协议栈中。注意做完之后需要重新在RX ring中分配一个mbuf和描述符，这样硬件才能把包放进来。

测试方法：首先在host上`make server`，然后`make qemu`并在xv6中运行`nettests`，`nettests`会向host上的`server`发一个UDP包，然后`server`会回一个包。但实际上`server`在发reply包之前，会先向xv6发送一个ARP请求包去获取它的48位以太网地址，并且期望xv6发回一个ARP包。

挑战如下：

* 发包也使用中断，将要发的包缓存起来，收到TX中断之后再通过TX ring发新的包，这样有可能做到优先发重要的包。
* 完整实现一套ARP cache机制。
* E1000支持多对RX和TX ring，配置E1000使得每个核使用一对，这将可能提升网络栈的吞吐量，因为减小了锁竞争。
* `socketrecvudp`使用一个链表查找目标socket，替换为hashtable和RCU提高性能。
* 使用ICMP协议检测失败的网络流并将错误传播到socket syscall接口。
* E1000提供若干无状态的硬件级别额外功能，比如计算校验和、RSC和GRO，利用这些功能进一步提升网络协议栈性能。
* 这个lab中的网络协议栈被怀疑可能有活锁问题，找出并解决之。
* 为xv6实现一个udp server应用。
* 实现一个最小化的tcp协议栈并下载一个web页面。

## 8 locks

重新设计代码提高锁粒度。

内存分配器：kalloctest是xv6内存分配器的压力测试，其中有三个进程并发不断grow和shrink他们的地址空间，因此会有很多kalloc和kfree的调用，一开始它们是用一把`kmem.lock`大锁保护的。我们会统计内核中每把锁`acquire`的次数以及`acquire`失败的次数。失败的比例可以近似衡量锁竞争的激烈度。提示：在测试的时候最好只开qemu，不要有其他负载，不然数据可能会不准。锁竞争的原因在于`kalloc`使用一个全局链表，使用一把全局大锁保护。做法是使用per-CPU的链表，难点是当一个core要分配内存的时候，local上没有空余内存了，此时就要从其他CPU上偷一些。有趣的是xv6提供了一个race detector也就是KCSAN，叫做Kernel Concurrency Sanitizer。如果检测出并发冲突的话，KCSAN会打印两个stacktrace，仍然可以使用addr2line工具查看。然而，即使没有检测出并发冲突，也不意味着就没有。

buffer cache：改成hash表的per-bucket lock。

挑战：使用LRU算法管理buffer；将bcache改成无锁实现。

## 9 file system

大文件支持：这个我们基本上已经支持了。

符号链接（软链接）：实现`symlink(char *target, char *path)`syscall，在`path`处创建一个指向`target`的软链接。做法：新建一种`T_SYMLINK`的文件类型；新增一种`open`syscall使用的`O_NOFOLLOW`标志位；新增`symlink`syscall，需要在磁盘数据块中保存软链接`path`指向的路径`target`，像`link`和`unlink`一样`symlink`也可能失败，失败的时候返回-1；在`open`的时候支持软链接，如果有`O_NOFOLLOW`标志位的话就不走软链接，如果软链接指向的文件还是软链接就递归处理，为了避免环形引用，可以当超过最大深度（比如10）之后返回error code；其他syscall，比如link和unlink不要走软链接。

挑战：更大文件的支持，3级indirect。

## 10 mmap

实现mmap syscall。mmap API如下：

```c
void *mmap(void *addr, size_t length, int prot, int flags,
           int fd, off_t offset);
```

这里假定`addr`为0，也就是kernel自行决定映射到应用地址空间的位置。mmap返回映射到的地址，若为0xFFFF_FFFF_FFFF_FFFF则表示失败。`length`表示映射的长度，未必与文件的长度相同。`prot`表示这块虚拟地址区域的访问权限，只需考虑`PROT_READ`和`PROT_WRITE`。flags可能为`MAP_SHARED`表示对于虚拟地址区域的修改将被写回到文件，而`MAP_PRIVATE`则不用。`fd`是要映射的一个打开的文件描述符。可以假定`offset`为0，也就是从文件的开头开始映射。

如果多个进程映射相同的`MAP_SHARED`文件，允许它们映射到不同的物理页上。

`munmap`取消映射，而且如果此前用`MAP_SHARED`映射的话，此时需要将修改写回到文件中。`munmap`可能只会取消映射一部分`mmap`的空间，但要么是一个前缀，要么是一个后缀，要么完全回收，这意味着`munmap`之后始终还是只有一段连续区间而不会分裂成多个。

挑战：

* 如果两个进程映射了相同的文件，让他们共享相同的物理页面。需要reference count。
* 在读一个mmap映射的页的时候，检查数据是否已经在buffer cache中了，如果已经存在的话就不要新建一个物理页面并拷贝数据了。同样需要考虑引用计数。
* 去掉懒分配和mmap机制之间的冗余，比如，给懒分配区域创建一个VMA。
* 修改`exec`使得二进制的每个段使用一个VMA，这样可以实现ELF的按需加载，使得启动速度大幅提高。
* 实现虚拟页面从物理内存和磁盘之间的换入换出机制。



