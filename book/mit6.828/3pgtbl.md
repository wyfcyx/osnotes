# pgtbl

## 实验指导书阅读

页表的标志位表示相关联的虚拟地址对于映射到的物理内存的访问权限。这可能是一种更好的说法。

虚拟内存并不是物理实体，它表示内核提供的复用物理内存的一系列机制和抽象。

### 内核地址空间

xv6 中，每个用户进程一个用户地址空间，内核只有一个内核地址空间。

和之前所想一致，xv6 的内核地址空间的设备区域和整块物理内存（在 `PHYSTOP` 以下）都是恒等映射过去的。然后，内核地址空间最高的一个页面是 trampoline 页，用来保证 trap 处理不出问题。接着似乎就是从这里开始往下分配带有 guard 页的内核栈，每个进程一个。

恒等映射有一个好处，就是在 `fork` 复制地址空间的时候很好用。（这是因为内核与用户地址空间隔离了才可以这样做）。内核地址空间中有这些区域不是恒等映射的，比如 trampoline 页（它被映射了两次，有两个虚拟地址可以访问，分别是地址空间最高的一个页和物理内存区域的某个页）。还有就是每个进程的内核栈，带有一个 guard 页防止内核栈溢出。（但是这个应该是每个函数需要的栈空间小于 4K 才有效，大多数情况下能起作用，但也会在某些情况下检测不出来）

### 创建地址空间

地址空间和页表的相关代码在 `vm.c` 中。

`pagetable_t` 实际上只是一个 `uint64*`，全局变量 `kernel_pagetable` 指向一个地址空间的根页表所在的物理页面，这个地址空间可能是内核地址空间，也有可能是某个进程的用户地址空间。

比较重要的函数有 `walk`，可以根据虚拟地址找到页表项；还有 `mappages`，可以映射新的页面。以 `kvm` 开头的函数操作内核地址空间；以 `uvm` 开头的函数操作用户地址空间。其他的函数则是同时作用于内核/用户地址空间。`copyout` 和 `copyin` 将数据拷贝到用户虚拟地址或者从用户虚拟地址读数据，它们在 `vm.c` 中，因为需要手动查页表。

启动的时候，在主函数 `main` 中会调用 `kvminit` 函数来创建内核页表。它首先分配一个物理页面作为内核页表的根页表。然后调用 `kvmmap` 来新增一些必要的映射，包括设备 MMIO 区域、物理内存以及 trampoline 页。

`kvmmap` 可以将一个虚拟地址区间映射到一个物理地址区间，它通过 `mappages`  来实现。`mappages` 则是对于每个虚拟页，调用 `walk` 找到对应的页表项（中间可能会分配一些新的物理页帧），并进行修改。

`walk` 模拟硬件手动查页表，如果查的过程中遇到了不合法的情况，在传入参数 `alloc` 不为 0 的情况下，会新分配一个物理页帧来保存页表并继续往下。最后的返回值就是找到的页表项的虚拟地址（由于恒等映射等于物理地址）。

后面主函数 `main` 会调用 `kvminithart` 来修改每个 hart 的 `satp` 寄存器为我们新创建的内核页表。由于物理内存部分是恒定映射，并不会影响切换之后的执行。

`proc.c` 中的 `procinit` 会为每个进程分配一个内核栈，每个进程的内核栈随着所在进程在全局数组 `proc` 中的位置是固定的。我们通过 `kvmmap` 来新增相应的映射，并通过 `kvminithart` 来刷新 TLB。xv6 中一共有两个地方用到了 `sfence.vma` 来刷新 TLB，分别是 `kvminithart` 修改 `satp` 之后，以及在 trampoline 部分回到 user 之前改回用户页表之后。

### 物理内存分配器

参考 `kalloc.c`。比较简单就不用记录了。

### 进程地址空间

当一个进程需要更多虚拟内存来使用的时候，我们需要分配若干物理页帧，然后在用户页表中进行映射，需要包含 RWXVU 标志位。

运行栈的大小为一个页面，在运行栈上面也加入了 guard 页防止栈溢出。在进程开始执行之前，内核要负责在进程的运行栈上**压入必要的命令行参数**，并修改 `a0,a1` 寄存器分别表示 `int argc` 和 `char* argv[]`。大体上，先压入所有的参数字符串本体，再压入他们的地址作为数组 `argv[]`。然后压入 `argc`。最后，是用户程序的结束之后的跳转地址。这个似乎没什么用，因为用户程序都是通过 `exit` 系统调用来退出的，而不是通过 `ret` 指令。

### sbrk

`sbrk` 是一个支持动态增长或缩减进程虚拟内存的系统调用。它在 `proc.c` 的 `growproc` 函数中实现，取决于增长还是缩减，会分别调用 `uvmalloc` 或 `uvmdealloc` 函数。注意 `uvmdealloc` 会通过 `kfree` 释放掉不再被用到的物理页帧。

事实上，我们只有在进程页表中才能知道物理页帧的去向。

### exec

其他的都比较传统。比较有意思的是内核/用户地址空间隔离就能够对用户程序做更多的检查，用户程序也不再能通过构造段的和内核段重复的位置来让加载用户程序的时候内核覆盖掉自己的段，这是类似于注入的危险行为。实际上还有更多检查。

### 堆内存分配

xv6 里面好像分配内核数据结构的时候都是直接分配一个页。果然在模拟器上就是可以为所欲为的。

## lab: print

```diff
diff --git a/kernel/defs.h b/kernel/defs.h
index a73b4f7..ebc4cad 100644
--- a/kernel/defs.h
+++ b/kernel/defs.h
@@ -178,6 +178,7 @@ uint64          walkaddr(pagetable_t, uint64);
 int             copyout(pagetable_t, uint64, char *, uint64);
 int             copyin(pagetable_t, char *, uint64, uint64);
 int             copyinstr(pagetable_t, char *, uint64, uint64);
+void            vmprint(pagetable_t);
 
 // plic.c
 void            plicinit(void);
diff --git a/kernel/exec.c b/kernel/exec.c
index 0e8762f..5440108 100644
--- a/kernel/exec.c
+++ b/kernel/exec.c
@@ -116,6 +116,8 @@ exec(char *path, char **argv)
   p->trapframe->sp = sp; // initial stack pointer
   proc_freepagetable(oldpagetable, oldsz);
 
+  if (p->pid == 1)
+    vmprint(p->pagetable);
   return argc; // this ends up in a0, the first argument to main(argc, argv)
 
  bad:
diff --git a/kernel/vm.c b/kernel/vm.c
index bccb405..e29cbda 100644
--- a/kernel/vm.c
+++ b/kernel/vm.c
@@ -440,3 +440,32 @@ copyinstr(pagetable_t pagetable, char *dst, uint64 srcva, uint64 max)
     return -1;
   }
 }
+
+void vmprintrecursive(pagetable_t pagetable, int depth)
+{
+  int index;
+  for (index = 0; index < 512; index++)
+  {
+    uint64 pte = *(pagetable + index);
+    if (!(pte & PTE_V))
+      continue;
+    uint64 pa = PTE2PA(pte);
+    int i;
+    for (i = 0; i < depth; i++)
+    {
+      if (i)
+        printf(" ");
+      printf("..");
+    }
+    printf("%d: pte %p pa %p\n", index, pte, pa);
+    if (depth < 3)
+      vmprintrecursive((pagetable_t)pa, depth + 1);
+  }
+}
+
+void vmprint(pagetable_t pagetable)
+{
+  printf("page table %p\n", pagetable);
+  vmprintrecursive(pagetable, 1);
+}
+
```

就是打印一下页表，很简单。

## lab: per-process-pgtbl-1

```diff
diff --git a/kernel/defs.h b/kernel/defs.h
index ebc4cad..441c8f4 100644
--- a/kernel/defs.h
+++ b/kernel/defs.h
@@ -179,6 +179,8 @@ int             copyout(pagetable_t, uint64, char *, uint64);
 int             copyin(pagetable_t, char *, uint64, uint64);
 int             copyinstr(pagetable_t, char *, uint64, uint64);
 void            vmprint(pagetable_t);
+void            freewalkincludeleaves(pagetable_t);
+uint64          walkaddrkernel(pagetable_t, uint64);
 
 // plic.c
 void            plicinit(void);
diff --git a/kernel/proc.c b/kernel/proc.c
index dab1e1d..43ec450 100644
--- a/kernel/proc.c
+++ b/kernel/proc.c
@@ -21,6 +21,9 @@ static void freeproc(struct proc *p);
 
 extern char trampoline[]; // trampoline.S
 
+extern pagetable_t kernel_pagetable;
+extern char etext[];
+
 // initialize the proc table at boot time.
 void
 procinit(void)
@@ -28,6 +31,7 @@ procinit(void)
   struct proc *p;
   
   initlock(&pid_lock, "nextpid");
+
   for(p = proc; p < &proc[NPROC]; p++) {
       initlock(&p->lock, "proc");
 
@@ -121,6 +125,31 @@ found:
     return 0;
   }
 
+  /*
+  pagetable_t temp = kernel_pagetable;
+  kvminit();
+  p->kpagetable = kernel_pagetable;
+  kernel_pagetable = temp;
+   */
+  pagetable_t kpagetable = (pagetable_t) kalloc();
+  memset(kpagetable, 0, PGSIZE);
+  mappages(kpagetable, UART0, PGSIZE, UART0, PTE_R | PTE_W);
+  mappages(kpagetable, VIRTIO0, PGSIZE, VIRTIO0, PTE_R | PTE_W);
+  mappages(kpagetable, CLINT, 0x10000, CLINT, PTE_R | PTE_W);
+  mappages(kpagetable, PLIC, 0x400000, PLIC, PTE_R | PTE_W);
+  // map kernel text executable and read-only.
+  mappages(kpagetable, KERNBASE, (uint64)etext-KERNBASE, KERNBASE, PTE_R | PTE_X);
+  // map kernel data and the physical RAM we'll make use of.
+  mappages(kpagetable, (uint64)etext, PHYSTOP-(uint64)etext, (uint64)etext, PTE_R | PTE_W);
+  // map the trampoline for trap entry/exit to
+  // the highest virtual address in the kernel.
+  mappages(kpagetable, TRAMPOLINE, PGSIZE, (uint64)trampoline, PTE_R | PTE_X);
+  p->kpagetable = kpagetable;
+
+  uint64 kstackva = KSTACK((int) (p - proc));
+  uint64 kstackpa = walkaddrkernel(kernel_pagetable, kstackva);
+  mappages(p->kpagetable, kstackva, PGSIZE, kstackpa, PTE_R | PTE_W);
+
   // Set up new context to start executing at forkret,
   // which returns to user space.
   memset(&p->context, 0, sizeof(p->context));
@@ -141,6 +170,8 @@ freeproc(struct proc *p)
   p->trapframe = 0;
   if(p->pagetable)
     proc_freepagetable(p->pagetable, p->sz);
+  if(p->kpagetable)
+    freewalkincludeleaves(p->kpagetable);
   p->pagetable = 0;
   p->sz = 0;
   p->pid = 0;
@@ -473,11 +504,14 @@ scheduler(void)
         // before jumping back to us.
         p->state = RUNNING;
         c->proc = p;
+        w_satp(MAKE_SATP(p->kpagetable));
+        sfence_vma();
         swtch(&c->context, &p->context);
 
         // Process is done running for now.
         // It should have changed its p->state before coming back.
         c->proc = 0;
+        w_satp(MAKE_SATP(kernel_pagetable));
 
         found = 1;
       }
diff --git a/kernel/proc.h b/kernel/proc.h
index 9c16ea7..0d5b78c 100644
--- a/kernel/proc.h
+++ b/kernel/proc.h
@@ -98,6 +98,7 @@ struct proc {
   uint64 kstack;               // Virtual address of kernel stack
   uint64 sz;                   // Size of process memory (bytes)
   pagetable_t pagetable;       // User page table
+  pagetable_t kpagetable;
   struct trapframe *trapframe; // data page for trampoline.S
   struct context context;      // swtch() here to run process
   struct file *ofile[NOFILE];  // Open files
diff --git a/kernel/vm.c b/kernel/vm.c
index e29cbda..dd3c137 100644
--- a/kernel/vm.c
+++ b/kernel/vm.c
@@ -111,6 +111,25 @@ walkaddr(pagetable_t pagetable, uint64 va)
   return pa;
 }
 
+uint64 walkaddrkernel(pagetable_t pagetable, uint64 va)
+{
+  pte_t pte;
+  uint64 pa;
+  for (int level = 2; level >= 0; --level)
+  {
+    uint64 idx = PX(level, va);
+    pte = pagetable[idx];
+    if (!(pte & PTE_V))
+    {
+      return 0;
+    }
+    pa = PTE2PA(pte);
+    if (level > 0)
+      pagetable = (pagetable_t) pa;
+  }
+  return pa;
+}
+
 // add a mapping to the kernel page table.
 // only used when booting.
 // does not flush TLB or enable paging.
@@ -289,6 +308,25 @@ freewalk(pagetable_t pagetable)
   kfree((void*)pagetable);
 }
 
+void freewalkincludeleaves(pagetable_t pagetable)
+{
+  for (int i = 0; i < 512; i++)
+  {
+    pte_t pte = pagetable[i];
+    if (pte & PTE_V)
+    {
+      uint64 pa = PTE2PA(pte);
+      if (!(pte & (PTE_R | PTE_W | PTE_X)))
+      {
+        // non leaf, recursive
+        freewalkincludeleaves((pagetable_t)pa);
+      }
+    }
+    pagetable[i] = 0;
+  }
+  kfree((void*)pagetable);
+}
+
 // Free user memory pages,
 // then free page-table pages.
 void
```

坑1：`walkaddr` 默认是在用户态调用，因此遇到 `PTE_U` 未被标志的情况会直接返回 0。这个是用在给每个进程里面的内核页表映射上当前进程的内核栈的。我们不能重新分配一个物理页帧，而是要从 `kernel_pagetable` 里面查到之前分配的物理页帧，然后在当前进程的内核页表里面直接映射过去。由于上述问题，不能调用 `walkaddr` 而是需要自己实现一个函数 `walkaddrkernel`。

坑 2：在 `freewalkincludeleaves` 回收存储页表的物理页帧的时候，将叶子的判定条件弄反了。导致在运行 `userstest` 的时候内存耗尽了。

## lab: per-process-pgtbl-2

往下写发现之前的理解很不到位，甚至上一个 lab 的话也是稍微换一种写法比较好。

在 `vm.c` 里面加入一个新的分配进程独立内核页表的函数：

```c
extern char etext[];

/*
 * create a new kvm, return its pagetable
 * include: MMIO/ kernel code/ other physical memory/ trampoline page
 * exclude: kernel stack & guard pages
 */
pagetable_t newkvm()
{
  pagetable_t kpagetable = (pagetable_t) kalloc();
  memset(kpagetable, 0, PGSIZE);
  mappages(kpagetable, UART0, PGSIZE, UART0, PTE_R | PTE_W);
  mappages(kpagetable, VIRTIO0, PGSIZE, VIRTIO0, PTE_R | PTE_W);
  // drop CLINT for the reason that it is only used very early stage
  // mappages(kpagetable, CLINT, 0x10000, CLINT, PTE_R | PTE_W);
  mappages(kpagetable, PLIC, 0x400000, PLIC, PTE_R | PTE_W);
  // map kernel text executable and read-only.
  mappages(kpagetable, KERNBASE, (uint64)etext-KERNBASE, KERNBASE, PTE_R | PTE_X);
  // map kernel data and the physical ram we'll make use of.
  mappages(kpagetable, (uint64)etext, PHYSTOP-(uint64)etext, (uint64)etext, PTE_R | PTE_W);
  // map the trampoline for trap entry/exit to
  // the highest virtual address in the kernel.
  mappages(kpagetable, TRAMPOLINE, PGSIZE, (uint64)trampoline, PTE_R | PTE_X);
  return kpagetable;
}
```

它包括一般内核页表除了内核栈之外的一切东西，有设备和物理内存的恒等映射，还有 trampoline 页，但是内核栈和相应的 guard page 都是没有的。注意我们不对 CLINT 的 MMIO 进行映射，参见坑 2。

因此，在 `allocproc` 里面也要进行相应替换。

```c
p->kpagetable = newkvm();
```

至此，上个 step 仍然能跑通。

这一步要做的事情是，将 `copyin` 的实现替换成 `vmcopyin.c` 里面的 `copyin_new`。`copyin` 的作用是从用户地址空间复制数据到内核地址空间。而在 `copyin_new` 里面是直接在内核地址空间里面 `memmove`，这就需要进程独有的页表 `kpagetable` 包含跟用户地址空间映射到相同的物理页面，只需考虑代码、数据段即可，无需考虑 trampoline 页（在 `kpagetable` 中已经有了）和 trap frame（在 `kpagetable` 里面是一个 guard page）。

首先完成替换：

```c
int
copyin(pagetable_t pagetable, char *dst, uint64 srcva, uint64 len)
{
  /*
  uint64 n, va0, pa0;

  while(len > 0){
    va0 = PGROUNDDOWN(srcva);
    pa0 = walkaddr(pagetable, va0);
    if(pa0 == 0)
      return -1;
    n = PGSIZE - (srcva - va0);
    if(n > len)
      n = len;
    memmove(dst, (void *)(pa0 + (srcva - va0)), n);

    len -= n;
    dst += n;
    srcva = va0 + PGSIZE;
  }
  return 0;
   */
  return copyin_new(pagetable, dst, srcva, len);
}
```

然后只要是涉及到用户地址空间的代码、数据段发生变化的情况，我们都要在 `kpagetable` 做同样的改变。

首先是第一个进程 `init`。参考 `userinit` 函数，里面通过 `uvminit` 给用户地址空间映射了一个物理页面。所以我们只需找到这个物理页面的位置，在 `kpagetable` 里面同样映射过去就好了。

这里有一个坑就是 `sstatus.sum` 全程没有打开，因此手动查页表可以，在内核态通过 MMU 访问 U 标记的虚拟地址就会 page fault。

在 `vm.c` 里面实现一个新的函数：

```c
int kpagetablecopy(pagetable_t pagetable, pagetable_t kpagetable, uint64 base, uint64 sz)
{
  for (uint64 a = base; a < base + sz; a += PGSIZE)
  {
    // we can use walk since it does not check PTE_U
    pte_t *pte = walk(pagetable, a, 0);
    uint64 pa = PTE2PA(*pte);
    int flags = PTE_FLAGS(*pte);
    if (flags & PTE_U)
      flags -= PTE_U;
    // otherwise: guard page of running stack
    if (mappages(kpagetable, a, PGSIZE, pa, flags) < 0)
      return -1;
  }
  return 0;
}
```

这里的从用户页表里面查到的 `flags` 可能不带有 `U` 标记，因为 `exec` 分配用户运行栈的时候会在下面分配一个 guard page 阻止用户态访问，参考坑 1；`mappages` 也涉及到物理页帧分配，在极端情况下可能 oom，此时需要整体返回 0，参考坑 3。

在 `userinit` 里面加入一行：

```c
// allocate one user page and copy init's instructions
// and data into it.
uvminit(p->pagetable, initcode, sizeof(initcode));
p->sz = PGSIZE;
/* add */
kpagetablecopy(p->pagetable, p->kpagetable, PGSIZE);
```

然后 `fork, exec, sbrk` 会导致用户代码、数据段的修改。

先来看 `fork`。在 `allocproc` 之后，我们知道 `np->pagetable` 里面只有 trampoline 页和 trapframe，而 `np->kpagetable` 里面有物理内存和 MMIO 的恒等映射、trampoline 页还有当前进程对应的内核栈。`fork` 只是通过 `uvmcopy` 将原来的 `p->pagetable` 复制到 `np->pagetable`。这里的 `uvmcopy` 是一个深拷贝，意味着会重新分配一些物理页面并复制数据。那么我们在 `np->kpagetable` 里面要做的同样是调用一下 `kpagetablecopy` 即可。

```c
// Copy user memory from parent to child.
if(uvmcopy(p->pagetable, np->pagetable, p->sz) < 0){
    freeproc(np);
    release(&np->lock);
    return -1;
}
kpagetablecopy(np->pagetable, np->kpagetable, p->sz);
np->sz = p->sz;
```

然后是 `exec`。这个在 `exec.c` 里面，涉及到命令行参数的传递显得有些复杂。我们可以省略掉前面的一些东西：

```c
// Commit to the user image.
oldpagetable = p->pagetable;
p->pagetable = pagetable;
p->sz = sz;
p->trapframe->epc = elf.entry;  // initial program counter = main
p->trapframe->sp = sp; // initial stack pointer
proc_freepagetable(oldpagetable, oldsz);
```

这里可以看出新的用户页表是 `pagetable`。我们需要调用 `proc_freepagetable` 回收掉旧页表并将 `p->pagetable` 替换为新页表。那么我们需要对 `p->kpagetable` 做的事情也是一样的。那么就是重新生成一个 `kpagetable`，初始化完了之后再切换 `satp`（实现的时候我曾经不小心把当前的 `satp` 回收掉了）。但是在极端情况下会浪费内存，参见坑 3。所以我们要在当前的 `p->kpagetable` 原地操作变更用户态。

```c
kpagetableinvalidate(p->kpagetable, 0, oldsz);
  if (kpagetablecopy(p->pagetable, p->kpagetable, 0, p->sz) < 0)
    panic("oom when exec!\n");
```

`kpagetableinvalidate` 实现如下：

```c
void kpagetableinvalidate(pagetable_t kpagetable, uint64 base, uint64 sz)
{
  for (uint64 a = base; a < base + sz; a += PGSIZE)
  {
    pte_t *pte = walk(kpagetable, a, 0);
    *pte = 0;
  }
}
```

最后是 `sbrk`。它的主要逻辑在 `growproc` 中，通过调用 `uvmalloc/uvmdealloc` 增长用户地址空间中数据段（需要新分配物理页面并映射）或者缩减（解映射并回收物理页面）。我们的 `kpagetable` 相应完成同步即可。这里面的小问题是 `oldsz` 和 `newsz` 都可以不对齐，因此需要判断一些边界条件。

在 `vm.c` 里面添加下面几个函数：

```c
int kpagetablealloc(pagetable_t pagetable, pagetable_t kpagetable, uint64 oldsz, uint64 newsz)
{
  if (newsz < oldsz)
    return 0;
  oldsz = PGROUNDUP(oldsz);
  for (uint64 a = oldsz; a < newsz; a += PGSIZE)
  {
    if (kpagetablecopy(pagetable, kpagetable, a, PGSIZE) < 0)
      return -1;
  }
  return 0;
}
void kpagetabledealloc(pagetable_t kpagetable, uint64 oldsz, uint64 newsz)
{
  oldsz = PGROUNDUP(oldsz);
  newsz = PGROUNDUP(newsz);
  if (newsz >= oldsz)
    return;
  kpagetableinvalidate(kpagetable, newsz, oldsz - newsz);
}
```

然后在 `growproc` 里面加入相应的 `kpagetable` 变更：

```c
if(n > 0){
  if((sz = uvmalloc(p->pagetable, sz, sz + n)) == 0) {
    return -1;
  }
  if (kpagetablealloc(p->pagetable, p->kpagetable, oldsz, oldsz + n) < 0)
    return -1;
} else if(n < 0){
  sz = uvmdealloc(p->pagetable, sz, sz + n);
  kpagetabledealloc(p->kpagetable, oldsz, oldsz + n);
}
```

注意在 `sbrk` 疯狂增长耗尽所有物理内存的时候，我们同样需要注意 `kpagetablealloc` 是否耗尽了物理页。

脑残错误1：回收 `kpagetable` 的时候忘了现在正在用它。

脑残错误2：`growproc` 利用使用了被修改之后的 `sz`。

脑残错误3：`exec` 里面玩起了新建一个 `kpagetable` 然后切换 `satp` 的操作，导致极限情况（丧心病狂的 `execout` 测试）下 `oom`，其实本来非常容易实现的。 

脑残错误4：不知道什么时候开始忘了把 `copyin` 换成 `copyin_new` 导致 `count copyin` 测试不能通过。这个测试模式挺值得学习的。就是在内核里面做一些统计，用户态获取统计结果并进行合法性验证。

坑1：用户页表里面的运行栈同样有一个 guard page。

坑2：说明中提到可以不在 `kpagetable` 中映射 CLINT 的 MMIO，但要确保用户段 size 不超过 PLIC。`growproc` 在适当的时候返回 0。

坑3：`execout` 这种极端测试会将所有内存全部耗尽（有点狠），所以我们自己实现的函数也要做相应的改动。在 `sbrk` 的时候如果耗尽了内存要直接返回 `-1`，也就是用户程序里面的 $2^{64}-1$。大概就是影响到 `kpagetablecopy` 和 `kpagetablealloc` 两个函数吧。
