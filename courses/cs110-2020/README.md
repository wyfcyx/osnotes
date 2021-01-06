# cs110 课件笔记

这门课是 Stanford 开的一门类似于 Linux 编程的课，简单过一遍好了。[课件链接](http://web.stanford.edu/class/cs110/slides-handouts.html)

## Lecture 02: Unix Filesystem API

首先是写了一个 `copy` 的 C 程序来模仿 `cp` 工具的功能。

在打开复制的目标文件的时候，使用的是 `O_WRONLY/O_CREAT/O_EXCL` 标志，其中 `O_EXCL` 表示必须**新建**文件，即如果同名文件已经存在会报错。

比较了直接使用文件描述符和 C 里面的 `FILE*`（或者 C++ 里面的 iostream）的优缺点：

* 文件描述符通常更快，可以用于网络，但只能使用 read/write 接口；
* `FILE*` 和 iostream 稍微慢一点，但是功能比较强大。

后面介绍了一下 Unix 内置的 `tee` 工具。它的功能是将标准输入中的所有内容复制到标准输出，但是这些内容也会被复制到参数中的那些文件里。

[We will be back](http://web.stanford.edu/class/cs110/lectures/02-slides.pdf)

