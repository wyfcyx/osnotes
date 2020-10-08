# syscall

通过做 lab 的方式来熟悉一下实验指导书，老角色扮演了。

## 内核代码分布

内核代码分布如下。

### 启动

`entry.S`：CPU 启动之后第一段代码，处于 M 特权级，设置启动栈并跳转到 `start.c` 中的 `start` 函数。

`start.c`：进行类似于 RustSBI 中的在 M 特权级的初始化，并最后通过 `mret` 返回到 S 特权级的 `main` 函数。

`main.c`：包括主函数 `main`，hart0 负责进行所有全局初始化，随后通过修改原子变量唤醒其他核，其他核只需进行局部初始化，随后所有核一起进入调度函数 `scheduler`。

### 驱动程序

`console.c`：与串口进行交互，可以读写字符，中断相关的逻辑也在其中。

`uart.c`：串口驱动程序。

`virtio_disk.c`：VirtIO 块设备驱动。

`plic.c`：PLIC 驱动。

### 简单工具库

`printf.c`：将 `console.c` 进一步包装，通过 `printf` 进行输出，方便调试。

`string.c`：C 字符串库，实用工具。

### Trap 处理

`kernelvec.S`：包含 `kernelvec`，这段汇编代码作用是保存中断上下文，调用 `kerneltrap` 函数，返回后恢复中断上下文；还包含 `timervec`，这是一段 M 特权级汇编，类比 RustSBI 中的软中断代理。因此 xv6 某个地方一定还有 M 特权级汇编来初始化这个东西。

`trampoline.S`：包含 `uservec` 和 `userret` 两段汇编，分别表示从 user 通过 trap 进入 kernel，和从 kernel 返回 user。在两段汇编中间，先调用 `usertrap` 函数，再调用 `usertrapret` 函数。这个只能在中断的时候再细看了。

`trap.c`：包含 `kerneltrap, usertrap, usertrapret` 等函数，负责中断的实际分发。

### 物理内存

`kalloc.c`：物理页帧分配器。

### 虚拟内存

`vm.c`：管理页表和地址空间。

### 进程调度

`proc.c`：进程之间运行状态的转换与调度。

`swtch.S`：通过汇编实现进程切换。

### 同步互斥

`spinlock.c`：基于原子指令实现的自旋锁。

`sleeplock.c`：基于进程调度实现的交出 CPU 使用权的休眠锁。

### 文件系统

`bio.c`：位于**块缓存层**，提供了块缓存类型 `bcache`，可以将若干磁盘块缓存在内存中。

`log.c`：位于**日志层**，将单个文件系统操作的多次块写入打包成一个原子事务。

`fs.c` ：位于**索引节点层**，描述索引节点的内容，并能够基于设计的存储布局获取或修改索引节点。

`file.c`：位于**文件描述符层**，提供了 Unix 资源单位类型 `file`，支持进程通过 fd 句柄进行访问，并将具体的读写任务转交给底层的具体资源来实现。注意系统内的所有资源会被缓存在全局资源表 `ftable` 中。

除了文件之外的其他资源：

`pipe.c`：另一种 Unix 资源管道，也会被封装到 Unix 资源单位 `file` 里面去；

### 系统调用

`syscall.c`：内核态系统调用入口，包含一些参数转换相关的实用函数。

`exec.c`：只包含系统调用 `exec`，替换当前进程的地址空间为指定程序并跳转到入口，支持带有 `argc, argv`。

`sysfile.c`：包含 Unix 资源相关的系统调用。

`sysproc.c`：包含进程调度相关的系统调用。

目前看到 2.5，有点累，明天再看。

## 进程

用户进程地址空间分布（从零开始向上增长）：首先是用户数据、代码段，然后是用户栈，然后是**用户**可以用来 malloc 的堆空间（注意这并不是内核堆）。最后是两个分别叫做 trapframe 和 trampoline 的页，与 user 切换到 kernel 有关。这个在 ch4 会提到。注意 xv6 基于 sv39 虚存模式，但是只用到 38 位虚拟地址。

进程控制块 PCB：

```c
// proc.h
// Per-process state
struct proc {
  struct spinlock lock;

  // p->lock must be held when using these:
  enum procstate state;        // Process state
  struct proc *parent;         // Parent process
  void *chan;                  // If non-zero, sleeping on chan
  int killed;                  // If non-zero, have been killed
  int xstate;                  // Exit status to be returned to parent's wait
  int pid;                     // Process ID

  // these are private to the process, so p->lock need not be held.
  uint64 kstack;               // Virtual address of kernel stack
  uint64 sz;                   // Size of process memory (bytes)
  pagetable_t pagetable;       // User page table
  struct trapframe *trapframe; // data page for trampoline.S
  struct context context;      // swtch() here to run process
  struct file *ofile[NOFILE];  // Open files
  struct inode *cwd;           // Current directory
  char name[16];               // Process name (debugging)
};	
```

PCB 最重要的内核状态：内核栈 `kstack`，页表 `pagetable` ，和中断上下文 `trapframe` 。

xv6 仅支持单线程进程，将执行流的运行状态也封装了进去使能任务切换。每个进程都有一个用户栈和内核栈（这和第二版是一样的）`p->kstack`。当执行用户代码的时候，该进程的内核栈是空的。当进程由于中断或系统调用进入内核态的时候，内核代码在内核态执行，当然用户态的执行现场还在用户栈上并没有丢失。

xv6 的 I/O 是阻塞式 I/O。

`p->state` 表明进程是否：已被分配、准备执行、正在执行、等待 I/O 或退出。

`p->pagetable` 保存进程地址空间对应的页表。

## xv6 启动与第一个进程

启动之后，位于 ROM 上的 bootloader 执行，将 xv6 复制到以 0x80000000 开头的内存中，并跳转到 0x80000000。

进入 `entry.S` 的 `_entry`，**多核**设置启动栈并跳转到 `start.c` 中的 `start`。这里进行一些 M 特权级初始化，如将 `satp` 修改为 0 禁用 MMU，进行一些中断代理，进行时钟中断的初始化。随后通过设置可以 `mret` 跳转到 S 特权级的处理入口，也就是 `main.c` 中的 `main`。

在 `main` 完成子系统和设备的初始化工作之后，会调用 `proc.c` 中的 `userinit` 创建第一个进程。第一个进程会在用户态执行 `user/initcode.S` 中的一小段汇编代码，但是它相当于是在里面调用了 `exec` 系统调用，所以会重返内核态，并用指定的程序（此时是 `/init`）替换到当前进程的地址空间与寄存器。我们可以在 `user/init.c` 中找到这第一个进程，它的功能是创建第一个终端设备文件，并打开标准输入、标准输出和标准错误输出。最后 `exec` 用户态终端程序 `sh`，内核就跑起来了。

## 从 user 进入 S 特权级 trap

整体的路径如下：首先是 `trampoline.S` 里面的 `uservec`，其次是 `trap.c` 里面的 `usertrap` 以及返回之后的 `usertrapret`，最后是 `trampoline.S` 里面的 `userret`，会通过 `sret` 回到用户态。

相比从内核进入 S 特权级 trap，从 user 进入会有更多挑战：首先是 `satp` 指向的是用户地址空间页表，它和内核地址空间是**隔离**的；其次 `sp` 寄存器的值可能是不合法甚至破坏性的。

因为硬件在进入 trap 的时候并不会切换页表，因此用户态地址空间要有 `trampoline.S` 这段汇编代码的映射，且必须和内核态地址空间映射到相同的虚拟地址。（这里貌似有点 tricky，感觉不是很有必要？）

xv6 的做法是用一个 *trampoline* 页（在 Linux 中看到过类似的东西）保存 `trampoline.S` 里面的代码，并且在用户/内核地址空间中都映射到相同的虚拟地址（某种程度上的共享内存）。这个虚拟地址被定义为 `TRAMPOLINE`，它正处在用户/内核地址空间中最高的 4KiB 位置上。

当要执行用户代码的时候，`stvec` 会被设置为 `uservec` 的地址。这样执行用户代码要进入 S 特权级 trap 的时候，就会执行 `uservec` 的一段汇编代码。这里首先要做的事情是，需要切换 `satp` 到内核页表，但我们还需要保持所有通用寄存器的值保持不变，即使想要将它们保存在栈上也一定会破坏某些寄存器，或者需要复杂的设计。这时候就需要另一个寄存器 `sscratch` 来进行暂时的周转。

事实上，我们首先通过 `csrrw` 将 `sscratch` 和 `a0` 寄存器进行交换，这样 `a0` 的值就保存在 `sscratch` 里面了。而在进入用户态之前，在内核态 `sscratch` 会被设置为每个进程独占的中断帧 `trapframe` 所在的位置。中断帧 `trapframe` 里面包含所有的通用寄存器（除 `x0`），当前进程的内核栈地址、当前 CPU 的编号、`usertrap` 的地址，以及内核页表的 `satp`。`uservec` 负责这些值，通过切换 `satp` 切换到内核地址空间，并调用 `usertrap`。

`usertrap` 完成中断的分发与返回。但是它首先会将 `stvec` 改成 `kernelvec`，这样如果在处理从用户态来的 trap 的时遇到中断，就会正确从 `kernelvec` 中进入了（这是某种程度上的 trap 嵌套）。同样的道理，它也需要将 `sepc` 保存在 trapframe 中，否则在这种情况下再次进入 trap ，`sepc` 就会被覆盖。接下来 `syscall` 和 `devintr` 分别处理系统调用和外部中断，如果不是这些情况，说明用户态执行代码时遇到了异常，**内核需要直接将这个进程杀死**。`syscall` 的情况会将 trapframe 中的 `sepc += 4`，因为无论如何返回 user 的时候将执行下一条指令。之后如果当前进程 PCB 的 `killed` 被标记为 true，会通过 `exit` 退出进程。时间片的设定也和第三版是一样的，只要遇到时钟中断直接 `yield` 进行进程切换。

接着，会调用 `usertrapret`。这个函数主要的作用是设置 CSR 从而迎接下一次从 user 进来的 trap。比如将 `stvec` 改回 `uservec`，准备 `uservec` 所依赖的 trapframe，并将 `sepc` 从 trapframe 取出还原成 user 进来时候的状态。最后调用 `userret`，这段汇编代码在 trampoline 页里面，内核/用户地址空间里面都映射了这一页，这样在 `userret` 里面切换了 `satp` 也能正常工作。

在调用 `userret` 之前，会将当前进程的用户地址空间页表 `satp` 并将地址空间中固定的保存 trapframe 的位置 `TRAPFRAME` 分别保存在 `a1,a0` 里面。首先是将页表切换到用户地址空间页表。`userret` 将 trapframe 内保存的来自 user 的 `a0` 复制到 `sscratch` 中准备后续与 `TRAPFRAME` 的交换。这样 `a0` 表示 `TRAPFRAME` 的位置，我们可以以它作为一个 base 来进行通用寄存器还原。接下来 `userret` 从 trapframe 里面取出除了 `a0` 之外的通用寄存器并还原，然后将 `a0` 和 `sscratch` 进行交换。于是 `a0` 被正确还原，`sscratch` 也保存了 `TRAPFRAME` 的位置，下次也能正确处理 trap。这样就可以通过 `sret` 返回 user 了。

## 系统调用

在传参的时候有一些小 trick。因为用户/内核地址空间除了 trampoline page 之外是完全隔离的，当用户在 syscall 的时候传入一个指针参数的时候，内核就需要手动查用户页表来找到相应的物理地址来获取实际的参数。

## lab: syscall tracing

只要按照实验说明一步一步来就可以。

```diff
diff --git a/.gitignore b/.gitignore
index b1d8932..53d8dd9 100644
--- a/.gitignore
+++ b/.gitignore
@@ -20,3 +20,4 @@ myapi.key
 xv6.out*
 .vagrant/
 submissions/
+.idea/
diff --git a/Makefile b/Makefile
index f0beb51..1c07efd 100644
--- a/Makefile
+++ b/Makefile
@@ -149,6 +149,7 @@ UPROGS=\
 	$U/_grind\
 	$U/_wc\
 	$U/_zombie\
+	$U/_trace\
 
 
 
diff --git a/kernel/proc.c b/kernel/proc.c
index 6afafa1..ebbed61 100644
--- a/kernel/proc.c
+++ b/kernel/proc.c
@@ -229,7 +229,7 @@ userinit(void)
   p->cwd = namei("/");
 
   p->state = RUNNABLE;
-
+  p->trace_mask = 0;
   release(&p->lock);
 }
 
@@ -294,6 +294,7 @@ fork(void)
   pid = np->pid;
 
   np->state = RUNNABLE;
+  np->trace_mask = p->trace_mask;
 
   release(&np->lock);
 
diff --git a/kernel/proc.h b/kernel/proc.h
index 9c16ea7..78ff58a 100644
--- a/kernel/proc.h
+++ b/kernel/proc.h
@@ -103,4 +103,5 @@ struct proc {
   struct file *ofile[NOFILE];  // Open files
   struct inode *cwd;           // Current directory
   char name[16];               // Process name (debugging)
+  int trace_mask;
 };
diff --git a/kernel/syscall.c b/kernel/syscall.c
index c1b3670..71800bc 100644
--- a/kernel/syscall.c
+++ b/kernel/syscall.c
@@ -104,6 +104,33 @@ extern uint64 sys_unlink(void);
 extern uint64 sys_wait(void);
 extern uint64 sys_write(void);
 extern uint64 sys_uptime(void);
+extern uint64 sys_trace(void);
+
+static char* syscall_names[] = {
+        "",
+        "fork",
+        "exit",
+        "wait",
+        "pipe",
+        "read",
+        "kill",
+        "exec",
+        "fstat",
+        "chdir",
+        "dup",
+        "getpid",
+        "sbrk",
+        "sleep",
+        "uptime",
+        "open",
+        "write",
+        "mknod",
+        "unlink",
+        "link",
+        "mkdir",
+        "close",
+        "trace",
+};
 
 static uint64 (*syscalls[])(void) = {
 [SYS_fork]    sys_fork,
@@ -127,6 +154,7 @@ static uint64 (*syscalls[])(void) = {
 [SYS_link]    sys_link,
 [SYS_mkdir]   sys_mkdir,
 [SYS_close]   sys_close,
+[SYS_trace]   sys_trace,
 };
 
 void
@@ -138,6 +166,8 @@ syscall(void)
   num = p->trapframe->a7;
   if(num > 0 && num < NELEM(syscalls) && syscalls[num]) {
     p->trapframe->a0 = syscalls[num]();
+    if ((p->trace_mask >> num) & 1)
+      printf("%d: syscall %s -> %d\n", p->pid, syscall_names[num], p->trapframe->a0);
   } else {
     printf("%d %s: unknown sys call %d\n",
             p->pid, p->name, num);
diff --git a/kernel/syscall.h b/kernel/syscall.h
index bc5f356..cc112b9 100644
--- a/kernel/syscall.h
+++ b/kernel/syscall.h
@@ -20,3 +20,4 @@
 #define SYS_link   19
 #define SYS_mkdir  20
 #define SYS_close  21
+#define SYS_trace  22
diff --git a/kernel/sysproc.c b/kernel/sysproc.c
index e8bcda9..e339093 100644
--- a/kernel/sysproc.c
+++ b/kernel/sysproc.c
@@ -95,3 +95,13 @@ sys_uptime(void)
   release(&tickslock);
   return xticks;
 }
+
+uint64
+sys_trace(void)
+{
+  int trace_mask = 0;
+  if (argint(0, &trace_mask) < 0)
+    return -1;
+  myproc()->trace_mask = trace_mask;
+  return 0;
+}
diff --git a/user/user.h b/user/user.h
index b71ecda..fdeeefc 100644
--- a/user/user.h
+++ b/user/user.h
@@ -23,6 +23,7 @@ int getpid(void);
 char* sbrk(int);
 int sleep(int);
 int uptime(void);
+int trace(int);
 
 // ulib.c
 int stat(const char*, struct stat*);
diff --git a/user/usys.pl b/user/usys.pl
index 01e426e..9c97b05 100755
--- a/user/usys.pl
+++ b/user/usys.pl
@@ -36,3 +36,4 @@ entry("getpid");
 entry("sbrk");
 entry("sleep");
 entry("uptime");
+entry("trace");
```

注意在 `userinit` 的时候也要将进程 `init` 的 `trace_mask` 初始化为 0。

## lab: sysinfo

添加一个新的系统调用的过程：

1. 在 `user/user.h` 中声明新的函数签名。
2. 在 `user/usys.pl` 中增加新的 entry，这样生成的 `usys.S` 会支持新的 syscall 对应的 ecall 汇编代码。从编译的角度，`user.h` 里面的应该是弱符号，这里的则是强符号。
3. 在 `kernel/syscall.h` 中增加新的 syscall ID。
4. 在 `kernel/syscall.c` 中新增 syscall 函数签名、系统调用名字数组以及转发桩函数。
5. 在合适的文件下面具体实现系统调用。

下面是相应修改：

```diff
diff --git a/Makefile b/Makefile
index 1c07efd..49dfd51 100644
--- a/Makefile
+++ b/Makefile
@@ -150,7 +150,7 @@ UPROGS=\
 	$U/_wc\
 	$U/_zombie\
 	$U/_trace\
-
+	$U/_sysinfotest\
 
 
 ifeq ($(LAB),trap)
diff --git a/kernel/defs.h b/kernel/defs.h
index 4b9bbc0..232b0fb 100644
--- a/kernel/defs.h
+++ b/kernel/defs.h
@@ -63,6 +63,7 @@ void            ramdiskrw(struct buf*);
 void*           kalloc(void);
 void            kfree(void *);
 void            kinit(void);
+uint64          get_freemem(void);
 
 // log.c
 void            initlog(int, struct superblock*);
@@ -104,6 +105,7 @@ void            yield(void);
 int             either_copyout(int user_dst, uint64 dst, void *src, uint64 len);
 int             either_copyin(void *dst, int user_src, uint64 src, uint64 len);
 void            procdump(void);
+int             get_nproc(void);
 
 // swtch.S
 void            swtch(struct context*, struct context*);
diff --git a/kernel/kalloc.c b/kernel/kalloc.c
index fa6a0ac..5e2d848 100644
--- a/kernel/kalloc.c
+++ b/kernel/kalloc.c
@@ -80,3 +80,18 @@ kalloc(void)
     memset((char*)r, 5, PGSIZE); // fill with junk
   return (void*)r;
 }
+
+uint64 get_freemem()
+{
+  struct run *r;
+  uint64 freemem = 0;
+  acquire(&kmem.lock);
+  r = kmem.freelist;
+  while (r)
+  {
+    freemem += PGSIZE;
+    r = r->next;
+  }
+  release(&kmem.lock);
+  return freemem;
+}
\ No newline at end of file
diff --git a/kernel/proc.c b/kernel/proc.c
index ebbed61..70d3fac 100644
--- a/kernel/proc.c
+++ b/kernel/proc.c
@@ -694,3 +694,16 @@ procdump(void)
     printf("\n");
   }
 }
+
+int get_nproc()
+{
+  struct proc *p;
+  int count = 0;
+  for (p = proc; p < &proc[NPROC]; p++) {
+    acquire(&p->lock);
+    if (p->state != UNUSED)
+      ++count;
+    release(&p->lock);
+  }
+  return count;
+}
diff --git a/kernel/syscall.c b/kernel/syscall.c
index 71800bc..357d85f 100644
--- a/kernel/syscall.c
+++ b/kernel/syscall.c
@@ -105,6 +105,7 @@ extern uint64 sys_wait(void);
 extern uint64 sys_write(void);
 extern uint64 sys_uptime(void);
 extern uint64 sys_trace(void);
+extern uint64 sys_sysinfo(void);
 
 static char* syscall_names[] = {
         "",
@@ -130,6 +131,7 @@ static char* syscall_names[] = {
         "mkdir",
         "close",
         "trace",
+        "sysinfo",
 };
 
 static uint64 (*syscalls[])(void) = {
@@ -155,6 +157,7 @@ static uint64 (*syscalls[])(void) = {
 [SYS_mkdir]   sys_mkdir,
 [SYS_close]   sys_close,
 [SYS_trace]   sys_trace,
+[SYS_sysinfo] sys_sysinfo,
 };
 
 void
diff --git a/kernel/syscall.h b/kernel/syscall.h
index cc112b9..0dfedc7 100644
--- a/kernel/syscall.h
+++ b/kernel/syscall.h
@@ -21,3 +21,4 @@
 #define SYS_mkdir  20
 #define SYS_close  21
 #define SYS_trace  22
+#define SYS_sysinfo 23
diff --git a/kernel/sysproc.c b/kernel/sysproc.c
index e339093..827546a 100644
--- a/kernel/sysproc.c
+++ b/kernel/sysproc.c
@@ -6,6 +6,7 @@
 #include "memlayout.h"
 #include "spinlock.h"
 #include "proc.h"
+#include "sysinfo.h"
 
 uint64
 sys_exit(void)
@@ -105,3 +106,17 @@ sys_trace(void)
   myproc()->trace_mask = trace_mask;
   return 0;
 }
+
+uint64
+sys_sysinfo(void)
+{
+  struct sysinfo info;
+  info.freemem = get_freemem();
+  info.nproc = get_nproc();
+  uint64 p;
+  if (argaddr(0, &p) < 0)
+    return -1;
+  if (copyout(myproc()->pagetable, p, (char*)&info, sizeof(info)) < 0)
+    return -1;
+  return 0;
+}
\ No newline at end of file
diff --git a/user/user.h b/user/user.h
index fdeeefc..6ba24e6 100644
--- a/user/user.h
+++ b/user/user.h
@@ -1,5 +1,6 @@
 struct stat;
 struct rtcdate;
+struct sysinfo;
 
 // system calls
 int fork(void);
@@ -24,6 +25,7 @@ char* sbrk(int);
 int sleep(int);
 int uptime(void);
 int trace(int);
+int sysinfo(struct sysinfo*);
 
 // ulib.c
 int stat(const char*, struct stat*);
diff --git a/user/usys.pl b/user/usys.pl
index 9c97b05..bc109fd 100755
--- a/user/usys.pl
+++ b/user/usys.pl
@@ -37,3 +37,4 @@ entry("sbrk");
 entry("sleep");
 entry("uptime");
 entry("trace");
+entry("sysinfo");
```

这里需要了解到的是：

1. `copyout` 的用法。参数分别是用户页表的指针，用户地址空间虚拟地址，内核地址空间虚拟地址以及拷贝大小。
2. `get_nproc` 的实现原理。所有的 PCB 都保存在一个大 `proc` 数组中。我们遍历该数组，找到其中状态不是 `UNUSED` 的 PCB。注意访问前后要加上 spinlock。
3. `get_freemem` 的实现原理。这个物理页帧分配器非常简单，就是一个链表，每个节点的内容只有指向下一个节点位置的一个指针。但是每个节点自己的地址也是有意义的，可以看成节点的实际内容。事实上每个节点代表一个可分配的物理页面，节点的位置就在该页面的开头 8 字节。在初始化的时直接操作物理地址，因此应该是在什么地方进行了**整块物理内存的恒等映射**。在访问前后同样要加上 spinlock。