# 文件系统的补充

看了一下 ostep，里面对于 fs 接口介绍更加详细。

很有趣的一种说法是：inode number 被称为一种 low-level 的文件名

目录可以读取，但是不能被用户手动修改（目录的权限与能否手动修改无关），只能通过创建/删除文件来间接修改

如果要引入目录的话，就得考虑命令行当前目录了，还需要考虑一下 . 和 ..

[这里](https://en.wikipedia.org/wiki/Unix_file_types)记录了unix 中的不同文件类型，在 `stat` 中进行显示的时候，标准文件代号`-`，目录代号`d`，符号链接`l`，命名管道`p`，Socket`s`，块设备特殊文件`b`，字符设备特殊文件`c`

一件有趣的事情：为何删除文件需要用 `unlink` 来实现？

> 所谓的 link 就是指从 human-readable 名字到 inode number(low-level filename) 之间的链接
>
> 在创建文件的时候就会进行硬链接了。每个 DiskInode/Inode 中也都会维护着硬链接计数。
>
> 当 inode 引用计数为0的时候，文件系统会将 inode 和对应的数据块自动回收，也就达到了删除文件的目的

相比硬链接，软链接能够链接到目录，且可以跨文件系统。软链接自身是一个文件，文件里的内容就是路径。

## 补充系统调用

* `fsync(fd)` 可以同步一个 ``fd`` 指向文件的修改回磁盘
* `lseek(fd, offset, whence)`，`whence` 有以下几种可能
  * `SEEK_SET` 表示直接设置 `offset`
  * `SEEK_CUR` 表示将当前的偏移量加上传入的 `offset`
  * `SEEK_END` 表示将当前的偏移量修改为当前文件的大小加上传入的 `offset`
* `dup(fd)`
* `linkat/unlink`
* `fstat(fd)` 或者 `stat(pathname)` 
* [``mkdirat``](https://www.man7.org/linux/man-pages/man2/mkdirat.2.html)

## 常见 unix 实用程序

* ls

  在ostep中，实现ls用到libc中的open/read/closedir三个接口

  但我们自己实现的话就直接从目录文件里面一个一个把dirent读出来即可

* stat

* echo

* cat

* mkdir

* rmdir(似乎只能删除一个空目录)

* ln链接

* rm(实现看起来比较复杂)

* mv(暂不考虑)

* 硬要说起来还有一个 chmod，暂时也不考虑

## shell 编写

一个简单的 unix shell parser，支持重定位和管道，产生式如下：

```
<command line>	::	<job>
				|	<job> '&'
				| 	<job> '&' <command line>
				|	<job> ';'
				|	<job> ';' <command line>
					         
<job>		::=	<command>
			|	< job > '|' < command >
					        
<command	::=	<simple command>
	        |	<simple command> '<' <filename>
	        |	<simple command> '>' <filename>
					        
<simple command>::=	<pathname>
	        	|	<simple command>  <token>
```

来自[这里](https://github.com/Swoorup/mysh)

对上面进行一些简化：

若干条管道 | | |
每个管道之间都是最开头一个应用 后面有许多命令行参数 也支持 < 和 > 的重定向
暂且不支持 || && 等shortcut

> - "A ; B"   Run A and then B, regardless of success of A
> - "A && B"  Run B if A succeeded
> - "A || B"  Run B if A failed
> - "A &"     Run A in background.

## 暂时不考虑的实现

* rename/renameat

## 已完成内容

* [x] 在 sys_exec 中支持传入命令行参数

  在 user_shell 中支持命令行参数解析

  在 user_lib 中支持将 argc/argv 传给 main 函数
  
* [x] 为了在 DiskInode 中能够放置更多内容，有必要支持二级间接索引

  目前单个 DiskInode 大小为 128 字节，其中直接索引 28 个块，同时带有一个一级间接索引和一个二级间接索引

  支持的单个总文件大小超过 8MiB，直接索引块的部分还可以用来保存其他元数据

  我这里希望能够加入一个访问权限要求，后面支持 link/unlink 之后可能还需要维护 nlinks

* [x] 添加了 cat 工具可以快速查看一个文件的内容

* [ ] 支持简单的输入/输出重定向

  这不仅需要强化 user_shell 的解析功能（目前，重定向只允许在末尾出现，且顺序必须为先输入后输出）

  还需要实现 dup 系统调用(syscall ID=24)

* [ ] 添加 stat 工具可以获取一个文件的元数据（目前包括文件类型，还有文件大小等内容）

  访问权限有点太苛刻了，其实只要知道是不是可执行文件就行了，但是这个也有点复杂了

  为此需要实现一个新的 stat 系统调用并在用户和内核态同时添加增加 FileStat 结构体

* [ ] 在 stat 基础上，添加 ls 工具可以输出根目录下所有文件的信息

