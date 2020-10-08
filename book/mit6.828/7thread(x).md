# thread

先吐槽一下，在 `git checkout thread` 的时候发现还没有这个分支。看了一下 schedule 发现 10 月 14 号才会开始这个实验。那这可就真的是纯口胡了。

## 实验指导书阅读

这里要求阅读完整的第六章文档还有相关的代码。（实际上在 2020 版指导书里面应该是第七章）

### 时分复用

在两种情况下 xv6 会进行进程切换：

1. 当一个进程等待某个事件（I/O 准备好，或者等待子进程退出，或者在 sleep 系统调用里面等待计时器超时）发生的时候，会用到 `sleep` 和 `wakeup` 机制。
2. 一个进程每运行（包括用户态/内核态）一个 tick 之后就会被内核强行切换出去。

相关挑战：

1. 如何从一个进程切换为另一个？
2. 如何以一种对于用户来说透明的方式完成进程切换？
3. 多核如何解决并发冲突；
4. 进程退出后所有的资源应该被回收，但是它无法自己回收自己的内核栈；
5. 多核情况下，每个核要保存自己核的运行状态；
6. sleep 和 wakeup 机制的正确实现。

### 进程切换

和 Tutorialv2 相同，xv6 里面的进程切换也实际上进行了两次切换：第一次是旧进程在 trap 的时候出于某种原因切换到 scheduler 内核线程；第二次是 scheduler 内核线程切换到新进程。每个 scheduler 内核线程都使用和进程的内核栈独立的栈。如果 scheduler 在旧进程的内核栈上执行的话会不安全：说是在 wakeup 机制下会导致两个 core 使用相同的栈，目前还不是很懂。

这里讲的是 kernel thread（指的是用户进程在内核态执行的部分） 和 scheduler thread 之前的切换。

进程切换函数实现两个 `struct context*` 之间的切换，将当前的寄存器状态保存在 `old` 里面，并从 `new` 里面读取寄存器状态并覆盖到当前寄存器上。

```assembly
# Context switch
#
#   void swtch(struct context *old, struct context *new);
# 
# Save current registers in old. Load from new.	
.globl swtch
swtch:
        sd ra, 0(a0)
        sd sp, 8(a0)
        sd s0, 16(a0)
        ...
        sd s11, 104(a0)

        ld ra, 0(a1)
        ld sp, 8(a1)
        ld s0, 16(a1)
        ...
        ld s11, 104(a1)
        
        ret
```

`context` 里面包含：

```c
// Saved registers for kernel context switches.
struct context {
  uint64 ra;
  uint64 sp;

  // callee-saved
  uint64 s0;
  uint64 s1;
  uint64 s2;
  uint64 s3;
  uint64 s4;
  uint64 s5;
  uint64 s6;
  uint64 s7;
  uint64 s8;
  uint64 s9;
  uint64 s10;
  uint64 s11;
};
```

而 `context` 出现在每个进程的 PCB 里面和每个 CPU 的执行状态 `struct cpu` 里面：

```c
// Per-CPU state.
struct cpu {
  struct proc *proc;          // The process running on this cpu, or null.
  struct context context;     // swtch() here to enter scheduler().
  int noff;                   // Depth of push_off() nesting.
  int intena;                 // Were interrupts enabled before push_off()?
};

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

比如在 `usertrap` 里面发现遇到了时钟中断会调用 `yield`。

```c
void
yield(void)
{
  struct proc *p = myproc();
  acquire(&p->lock);
  p->state = RUNNABLE;
  sched();
  release(&p->lock);
}
```

`yield` 会调用 `sched`：

```c
// Switch to scheduler.  Must hold only p->lock
// and have changed proc->state. Saves and restores
// intena because intena is a property of this
// kernel thread, not this CPU. It should
// be proc->intena and proc->noff, but that would
// break in the few places where a lock is held but
// there's no process.
void
sched(void)
{
  int intena;
  struct proc *p = myproc();

  if(!holding(&p->lock))
    panic("sched p->lock");
  if(mycpu()->noff != 1)
    panic("sched locks");
  if(p->state == RUNNING)
    panic("sched running");
  if(intr_get())
    panic("sched interruptible");

  intena = mycpu()->intena;
  swtch(&p->context, &mycpu()->context);
  mycpu()->intena = intena;
}
```

最关键的一步在于调用了 `swtch`，将寄存器状态从当前进程 trap 到 swtch 之前的执行状态（保存到 p->context）切换到当前核上 scheduler 的执行状态（从 mycpu()->context 恢复）。

注意 context 里面只保存了 ra, sp 和所有的被调用者保存寄存器。调用者保存寄存器是在执行 `swtch` 代码之前编译器为我们自动插入汇编代码保存的，它们其实也已经在栈上了，且我们清楚的知道整个 `swtch` 代码都没有修改它们，故无需再次保存。从这个角度上来讲，进程切换相当于开销较小的函数调用。 

注意 context 里面不会保存 pc 而是会保存 ra。这是因为在 swtch ret 之后，我们希望能从新执行流（之前一直停在 swtch 的位置）swtch 的下一条指令开始执行。因此只要保存 ra 寄存器就好了。

当前核 scheduler 的上下文保存在 `struct cpu` 中的 context 字段中，它在主调度函数第一次找到 *RUNNABLE* 的进程的时候被保存。

### 进程调度

一个想要放弃 CPU 使用权的进程必须获取它的进程锁 `p->lock`，并释放它目前持有的任何其他锁，更新它的运行状态 `p->state`，然后调用 `sched`。`yield/sleep/exit` 都遵从这样的规范。

`sched` 对于进程锁的持有情况进行了检查，此外，当持有锁的时候，**中断需要被关闭**。然后就是保存当前进程的 context，切换到 scheduler 的 context，继续跑 scheduler loop。

```c
// Per-CPU process scheduler.
// Each CPU calls scheduler() after setting itself up.
// Scheduler never returns.  It loops, doing:
//  - choose a process to run.
//  - swtch to start running that process.
//  - eventually that process transfers control
//    via swtch back to the scheduler.
void
scheduler(void)
{
  struct proc *p;
  struct cpu *c = mycpu();
  
  c->proc = 0;
  for(;;){
    // Avoid deadlock by ensuring that devices can interrupt.
    intr_on();

    for(p = proc; p < &proc[NPROC]; p++) {
      acquire(&p->lock);
      if(p->state == RUNNABLE) {
        // Switch to chosen process.  It is the process's job
        // to release its lock and then reacquire it
        // before jumping back to us.
        p->state = RUNNING;
        c->proc = p;
        swtch(&c->context, &p->context);

        // Process is done running for now.
        // It should have changed its p->state before coming back.
        c->proc = 0;
      }
      release(&p->lock);
    }
  }
}
```

考虑一下锁的使用。

比如在 `yield` 里面会 acquire 当前进程的锁，随后在 `sched` 里面会检查确实持有了当前进程的锁，而后通过 `swtch` 切换到当前核的 `scheduler`。它也是从一个 `swtch` 后面开始执行。注意由于当前核刚才正在执行当前进程，所以应该满足 `p == myproc()`。我们首先清空当前核的运行状态 `c->proc = 0`，然后再 release 掉当前进程的锁。

这样的话，如果有其他核正在等待 acquire 这个进程的锁的话，在上面的那个锁被释放之后，它就能够持有这个锁，修改进程的运行状态并修改当前核正在执行的进程为这个进程，然后 `swtch` 到这个进程停在的 `sched` 在 `swtch` 之后的位置（此时已经是在这个进程的内核栈上执行了），在 `sched` 返回之后，继而是在 `yield` 里面释放这个进程锁，最后 `yield` 返回。

这里锁的使用比较奇怪，因为它是非常罕见地在一个 core 上获取锁并在另一个 core 上释放。

使用锁的目的是保持某种不变性：至于是何种不变性这里先不详细分析。我们需要对那些访问了 PCB 可能产生并发冲突的数据段的操作加锁，使得只有在临界区可能出现不满足不变性的情况。但是这个确实很难设计。当前这种锁的粒度可以说已经比较细了。

### mycpu 和 myproc

```c
// proc.h
extern struct cpu cpus[NCPU];
// proc.c
struct cpu*
mycpu(void) {
  int id = cpuid();
  struct cpu *c = &cpus[id];
  return c;
}
```

`struct cpu` 里面维护了一个需要关闭中断的 spinlock 的**嵌套层数**。只有其变为 0 才能够打开中断。

至于 `cpuid` 是从 tp 寄存器中读取并保证在内核态始终不变。最开始在 `start.c` 中将 mhartid 保存在 tp 中。在 trampoline 中进行 user 和 kernel 切换的时候也保存和恢复了 tp，因为 user 可能修改这个寄存器。

`cpuid/mycpu` 的返回值在进程被移动到其他核上执行之后可能不再正确。因此 `mycpu` 的调用者要保证在使用 `mycpu` 的全程关闭中断。参考 `kerneltrap`，在内核态仍可能触发时钟中断。

```c
// Return the current struct proc *, or zero if none.
struct proc*
myproc(void) {
  push_off();
  struct cpu *c = mycpu();
  struct proc *p = c->proc;
  pop_off();
  return p;
}
```

注意 `push_off` 和 `pop_off` 看起来是在关闭、打开中断。但其实他们是 `spinlock.c` 提供的：

```c
// push_off/pop_off are like intr_off()/intr_on() except that they are matched:
// it takes two pop_off()s to undo two push_off()s.  Also, if interrupts
// are initially off, then push_off, pop_off leaves them off.

void
push_off(void)
{
  int old = intr_get();

  intr_off();
  if(mycpu()->noff == 0)
    mycpu()->intena = old;
  mycpu()->noff += 1;
}

void
pop_off(void)
{
  struct cpu *c = mycpu();
  if(intr_get())
    panic("pop_off - interruptible");
  if(c->noff < 1)
    panic("pop_off");
  c->noff -= 1;
  if(c->noff == 0 && c->intena)
    intr_on();
}

// riscv.h
// are device interrupts enabled?
static inline int
intr_get()
{
  uint64 x = r_sstatus();
  return (x & SSTATUS_SIE) != 0;
}
// enable device interrupts
static inline void
intr_on()
{
  w_sstatus(r_sstatus() | SSTATUS_SIE);
}
// disable device interrupts
static inline void
intr_off()
{
  w_sstatus(r_sstatus() & ~SSTATUS_SIE);
}
```

这里我们就能够看出 `struct cpu` 里面的 intena 保存的是第一次 `push_off` 之前是否打开了 sstatus.sie。

一般情况下我们都是直接用 `myproc`，它由于加上了 `push_off` 和 `push_on` 可以保证拿到的 `mycpu` 是对的，进而可以正确找到 `c->proc`。

### 挂起和唤醒

里面提到了一种称为 lost wakeup 的可能的 bug，大概就是在 consumer 判断到缓冲区里面没有东西，但还没有 sleep 之前，producer 向空缓冲区完成了加入。如此一来的话，在 producer 下一次 push 之前，consumer 都不会被唤醒。

下面是 `sleep` 和 `wakeup` 的实现：

```c
// Atomically release lock and sleep on chan.
// Reacquires lock when awakened.
void
sleep(void *chan, struct spinlock *lk)
{
  struct proc *p = myproc();
  
  // Must acquire p->lock in order to
  // change p->state and then call sched.
  // Once we hold p->lock, we can be
  // guaranteed that we won't miss any wakeup
  // (wakeup locks p->lock),
  // so it's okay to release lk.
  if(lk != &p->lock){  //DOC: sleeplock0
    acquire(&p->lock);  //DOC: sleeplock1
    release(lk);
  }

  // Go to sleep.
  p->chan = chan;
  p->state = SLEEPING;

  sched();

  // Tidy up.
  p->chan = 0;

  // Reacquire original lock.
  if(lk != &p->lock){
    release(&p->lock);
    acquire(lk);
  }
}

// Wake up all processes sleeping on chan.
// Must be called without any p->lock.
void
wakeup(void *chan)
{
  struct proc *p;

  for(p = proc; p < &proc[NPROC]; p++) {
    acquire(&p->lock);
    if(p->state == SLEEPING && p->chan == chan) {
      p->state = RUNNABLE;
    }
    release(&p->lock);
  }
}
```

这里面，进程锁 `p->lock` 主要用于保护 PCB 处于某种不变体。而 `chan` 就是一个 `void*`，伴生的 `lk` 主要用于保护含有这个 `void*` 的数据结构。在调用 `sleep` 之前需要持有 `lk`，然后我们在 `sched` 之前将其释放掉。

比较明显的例子就是在 `console.c` 中，`consoleread` 发现 ringbuffer 没有字符的时候会 `sleep(&cons.r, &cons.lock)`。而 `cons` 是一个这样的数据结构：

```c
struct {
  struct spinlock lock;
  
  // input
#define INPUT_BUF 128
  char buf[INPUT_BUF];
  uint r;  // Read index
  uint w;  // Write index
  uint e;  // Edit index
} cons;
```

在调用 `sleep` 之前我们的确持有了 `cons.lock`，因此在 `sleep` 里面调用 `sched` 之前需要将这个锁释放掉。然后被唤醒并在某个核上继续执行的时候，还会回到 `sleep` 里面尝试获取这个锁。注意在 `wakeup` 的时候跟这个伴生锁 `lk` 并没有关系。

当 `wait` 的时候会出现 `p->lock` 也就是 `lk` 的情况。这个后面再说。

### 管道

pipe 里面有一个 ringbuffer 和一个 spinlock。

```c
struct pipe {
  struct spinlock lock;
  char data[PIPESIZE];
  uint nread;     // number of bytes read
  uint nwrite;    // number of bytes written
  int readopen;   // read fd is still open
  int writeopen;  // write fd is still open
};
```

分析 `pipewrite` 和 `piperead` 的实现：

```c
int
pipewrite(struct pipe *pi, uint64 addr, int n)
{
  int i;
  char ch;
  struct proc *pr = myproc();

  acquire(&pi->lock);
  for(i = 0; i < n; i++){
    while(pi->nwrite == pi->nread + PIPESIZE){  //DOC: pipewrite-full
      if(pi->readopen == 0 || pr->killed){
        release(&pi->lock);
        return -1;
      }
      wakeup(&pi->nread);
      sleep(&pi->nwrite, &pi->lock);
    }
    if(copyin(pr->pagetable, &ch, addr + i, 1) == -1)
      break;
    pi->data[pi->nwrite++ % PIPESIZE] = ch;
  }
  wakeup(&pi->nread);
  release(&pi->lock);
  return i;
}

int
piperead(struct pipe *pi, uint64 addr, int n)
{
  int i;
  struct proc *pr = myproc();
  char ch;

  acquire(&pi->lock);
  while(pi->nread == pi->nwrite && pi->writeopen){  //DOC: pipe-empty
    if(pr->killed){
      release(&pi->lock);
      return -1;
    }
    sleep(&pi->nread, &pi->lock); //DOC: piperead-sleep
  }
  for(i = 0; i < n; i++){  //DOC: piperead-copy
    if(pi->nread == pi->nwrite)
      break;
    ch = pi->data[pi->nread++ % PIPESIZE];
    if(copyout(pr->pagetable, addr + i, &ch, 1) == -1)
      break;
  }
  wakeup(&pi->nwrite);  //DOC: piperead-wakeup
  release(&pi->lock);
  return i;
}
```

这里设计的巧妙性在于，读端进程会等在 `pi->nread` 这个 channel 上，而写端进程会等在 `pi->nwrite` 这个 channel 上。两个方法都会全程持有 `pi->lock`，但在 `sleep` 的时候也会释放掉来让另一端持有来工作，被唤醒之后会在 `sleep` 里面重新持有锁。

当写端发现 ringbuffer 已满的时候，会尝试唤醒所有读端，自己 sleep；但读端会在获取到锁之后立即检查目前有多少字符可以读，如果没有字符可以读的话会 sleep，但并不会唤醒写端。在两个方法即将退出并释放 `pi->lock` 之前，都会尝试唤醒对端。

### wait/exit/kill

当一个子进程退出，但父进程还没有 `wait` 的时候，子进程会被设置为 `ZOMBIE` 状态，在父进程 `wait` 之后，会将子进程设置为 `UNUSED` 状态从而可以在那一位置分配新进程，拷贝子进程的退出状态（这里就是一个 int 表示进程的返回值）到父进程的用户空间，并返回子进程的 pid。

如果父进程比子进程更早退出，那么父进程会将子进程的 parent 设置为最早的 init 进程，它会一直等待所有的子进程退出才会退出。这样的话可以保证所有的进程最终都会退出。

首先看 `wait`。注意 `wait` 只会等待一个子进程返回，所以等待所有子进程返回应该需要 `while` 循环直到 `wait` 返回值为 -1，即不存在任何子进程。

```c
int
wait(uint64 addr)
{
  struct proc *np;
  int havekids, pid;
  struct proc *p = myproc();

  // hold p->lock for the whole time to avoid lost
  // wakeups from a child's exit().
  // 首先直接获取锁避免 lost wakeup
  acquire(&p->lock);

  for(;;){
    // Scan through table looking for exited children.
    // 遍历 proc 表
    havekids = 0;
    for(np = proc; np < &proc[NPROC]; np++){
      // this code uses np->parent without holding np->lock.
      // acquiring the lock first would cause a deadlock,
      // since np might be an ancestor, and we already hold p->lock.
      // 访问 np->parent 不用加锁，反之如果这里加锁的话容易死锁
      if(np->parent == p){
        // np->parent can't change between the check and the acquire()
        // because only the parent changes it, and we're the parent.
        // 这里 np 的状态要发生变化了，必须上锁
        acquire(&np->lock);
        havekids = 1;
        if(np->state == ZOMBIE){
          // Found one.
          // 找到一个僵尸进程
          pid = np->pid;
          if(addr != 0 && copyout(p->pagetable, addr, (char *)&np->xstate,
                                  sizeof(np->xstate)) < 0) {
            release(&np->lock);
            release(&p->lock);
            return -1;
          }
          // 如果拷贝返回状态没出问题
          // 回收子进程
          freeproc(np);
          // 释放锁并直接返回这个子进程的结束状态
          release(&np->lock);
          release(&p->lock);
          return pid;
        }
        release(&np->lock);
      }
    }

    // No point waiting if we don't have any children.
    // 遍历了一轮 proc 表，没有发现一个子进程（无论它们处于什么状态），说明没有子进程，直接返回 -1
    if(!havekids || p->killed){
      release(&p->lock);
      return -1;
    }
    
    // 注意这里 sleep 的 lk 参数是一个当前进程的进程锁
    // 这样就解释了在 sleep 里面发现 p->lock == lk 的时候为何什么都不做
    // 我们仍需要保证进入 sched 的时候持有 p->lock
    // Wait for a child to exit.
    sleep(p, &p->lock);  //DOC: wait-sleep
  }
}
```

我们再来看 `exit`。它要做的事情是：记录返回状态、回收部分资源、将所有子进程的 parent 指向 init 进程、唤醒它的正处于 `wait` sleep 状态的父进程、将当前进程的 state 标记为 ZOMBIE 的同时也永久放弃 CPU 使用权。这里面对于锁的使用也很有技巧，我们姑且不去仔细研究。

```c
// Exit the current process.  Does not return.
// An exited process remains in the zombie state
// until its parent calls wait().
void
exit(int status)
{
  struct proc *p = myproc();

  if(p == initproc)
    panic("init exiting");

  // Close all open files.
  for(int fd = 0; fd < NOFILE; fd++){
    if(p->ofile[fd]){
      struct file *f = p->ofile[fd];
      fileclose(f);
      p->ofile[fd] = 0;
    }
  }

  begin_op();
  iput(p->cwd);
  end_op();
  p->cwd = 0;

  // we might re-parent a child to init. we can't be precise about
  // waking up init, since we can't acquire its lock once we've
  // acquired any other proc lock. so wake up init whether that's
  // necessary or not. init may miss this wakeup, but that seems
  // harmless.
  acquire(&initproc->lock);
  wakeup1(initproc);
  release(&initproc->lock);

  // grab a copy of p->parent, to ensure that we unlock the same
  // parent we locked. in case our parent gives us away to init while
  // we're waiting for the parent lock. we may then race with an
  // exiting parent, but the result will be a harmless spurious wakeup
  // to a dead or wrong process; proc structs are never re-allocated
  // as anything else.
  acquire(&p->lock);
  struct proc *original_parent = p->parent;
  release(&p->lock);
  
  // we need the parent's lock in order to wake it up from wait().
  // the parent-then-child rule says we have to lock it first.
  acquire(&original_parent->lock);

  acquire(&p->lock);

  // Give any children to init.
  reparent(p);

  // Parent might be sleeping in wait().
  wakeup1(original_parent);

  p->xstate = status;
  p->state = ZOMBIE;

  release(&original_parent->lock);

  // Jump into the scheduler, never to return.
  sched();
  panic("zombie exit");
}
```

`kill` 基本上只是将 PCB 里面的 killed 标记成 true。然后在适当的时候回收，暂时不细看。

## lab: uthread

现在还看不到代码。但总之是补全 `uthread.c` 使得能够实现一个 green thread 的功能。大体上每个 uthread 都需要有独立的栈，还要实现上下文切换。

## lab: using threads

这个实验在现有的 OS 上完成，基于 glibc 已有的 pthread 来探索并发程序开发。用到一个比较老的 [ph.c](https://pdos.csail.mit.edu/6.828/2018/homework/ph.c)。总体来说就是修改程序，减小锁的粒度来获得更优秀的并发性能。这个我以前好像做过，先不细究了。

## lab: barrier

基于 pthread 的 condition variable 实现一个 barrier，相关程序 [barrier.c](https://pdos.csail.mit.edu/6.828/2018/homework/barrier.c)。barrier 就是一个程序中的位置，所有的线程会在这里进行同步，等它们都执行到这个地方的时候，才能分别继续向下执行。好像不是很难，先略过了。

