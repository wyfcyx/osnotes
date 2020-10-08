# mmap

实现共享内存的系统调用 mmap：

```c
void *mmap(void *addr, size_t length, int prot, int flags,
           int fd, off_t offset);
```

这个 lab 只需要实现 memory-mapped files 功能。传入的 `addr` 永远为 0，意味着内核可以自己选择 mmap 的区域。`length` 为 mmap 的长度，它与文件的 size 可能不一样。`prot` 表明 mmap 的权限，即用户对于这段区域的访问权限，只可能是 `R` 或 `W` 或者都有。`flags` 里面只需要考虑 `MAP_SHARED` ，表明用户对于 mmap 的写入也将会被同步回文件；或者 `MAP_PRIVATE`，即用户对于 mmap 的写入不必同步回文件。`fd` 是之前打开文件的文件描述符，并可以认为 `offset` 永远为 0，即从文件的开头开始映射一段。

**允许** mmap 相同文件的不同进程在地址空间里面映射到不同的物理页帧，也就是说每次 mmap 的时候都重新分配一次物理页帧从文件里面复制数据即可。

`munmap(addr, length)` 在解映射 mmap 区域的同时，如果在 `mmap` 的时候 `MAP_SHARED`，在这个时候才会**第一次**将用户的修改同步回文件。`munmap` 可能只会解映射 `mmap` 区域的一部分，但是要么是一个前缀，要么是一个后缀。任何时候用户可用的 mmap 区域都是一段连续区间。

最后通过 `mmaptest` 即可。

提示：

* 类似 lazy allocation，在 mmap 的时候并不需要实际分配物理页帧。而是在 page fault 的时候再分配物理页帧并复制数据、完成实际映射。要求这个是为了保证 mmap 的速度，以及允许 mmap 一个超过内存大小的文件。
* 对于每个进程在 PCB 内保存映射了哪些 mmap，开一个**固定长度**的信息结构体数组（xv6 kernel 里面不支持内存分配），信息包括 addr, length, file, perm 等等。
* 实现 mmap：在用户页表里面找到一块未使用的区域作为 addr，在 PCB 里面加入 VMA 结构体，它要包含被映射到的文件的指针，需要增加 RC。即使在 mmap 之后通过 close 关闭文件也依然能够访问到里面的数据。
* 在 page fault 里面实现物理页帧分配、数据拷贝以及映射到进程的用户页表。
* 实现 munmap：在 PCB 里面找到相关的 VMA，更改 addr, length（由于它仍然是一个区间），解映射并回收物理页帧，如果 MAP_SHARED，则回收之前要写回文件。当区间彻底变为空集的时候，减少文件的 RC。
* 优化：通过 PTE_D 可以判断用户是否修改了 mmap 中的某个页。但是不用判断，直接全部写回文件也能通过。
* 相应修改 `fork` 和 `exit`。