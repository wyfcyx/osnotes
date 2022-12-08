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

## 8-pipes-and-ipc-1

background execution: (just an example)`fork`and`execve`,but do not `waitpid`; then, how can we reap the child?

2 ways of IPC: pipes & signals

## 9-pipes-and-ipc-2

## 10-signals-1

let two processes(or a process and OS) communicate with each other "indicating that something special has happened"

who can send the signal: a process or OS

`SIGSEGV`: from OS, default: termination

`SIGINT`: from OS to the foreground process group, default: termination

`SIGTSTP`: `^z`, from OS to the foreground process group, default: suspension

> `SIGTSTP` versus `SIGSTOP`: `SIGTSTP` can be ignored or handled while `SIGSTOP` cannot

`SIGCHLD`: when a child process changes its state, from OS to the parent process, application: reap a child via `waitpid` in the signal handler, default: ignore

`SIGPIPE`: wrote to a pipe that has no reader, from OS, default: terminate

`waitpid`: wait until a child process **changes its state**(by default: exit)

> options:
>
> * `WUNTRACED`: also wait a child to be stopped, `SIGSTOP` or something similar
> * `WCONTINUED`: also wait a child to be continued, `SIGCONT`
> * `WNOHANG`: non-blocking

two actions we can take related to signals : adding signal handlers(using `signal` or `sigaction`) or block until a signal comes in

signal handler does not stack: we only know that one *or more* signals were received, and we do not know the exact number

## 11-signals-2

signals like `SIGSEGV` or `SIGFPE` are called traps(due to the execution of the program, **immediately**)

signals like `SIGCHLD` or `SIGINT` are called interrupts(external and asynchronous events, **delayed, in the next time slice**)

`waitpid` with `WNOHANG` option: return 0 means that there are still some running child processes; return -1 means that no children are left

signal->asynchronous events->concurrency problems comes in!

avoid race conditions in signal handlers: only use signal-handler-safe functions

signals are error-prone, maybe the worst part of the UNIX's design

waiting for signals: handle pending signals at a proper time under the applications' consideration; more predictable(eliminate possible data races); but worse in terms of real-time

```c
// can only wait on asynchronous signals
int sigwait(const sigset_t *set, int *sig);
// creation and modification of sigset_t
// sigemptyset
// sigfillset
// sigaddset
// sigdelset
```

`sigprocmask`: forked child inherit blocked signals

## 12-signals-and-virtual-memory

