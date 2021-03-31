# trap

## 实验指导书阅读

之前跟 trap 相关的好像已经看过了，这次就直接看 lab。

## lab: RISC-V assembly

这个 lab 意在让学生理解调用规范。将一段非常简单的代码 `call.c` 编译并反汇编：

```c
#include "kernel/param.h"
#include "kernel/types.h"
#include "kernel/stat.h"
#include "user/user.h"

int g(int x) {
  return x+3;
}

int f(int x) {
  return g(x);
}

void main(void) {
  printf("%d %d\n", f(8)+1, 13);
  exit(0);
}
```

反汇编结果还提供源码对照，这个不知道是怎么来的。

依次回答几个问题：

1. 参数传递从左到右依次放在 a0, a1, a2 寄存器中，因此 printf 中的 13 放在 a2 寄存器中；
2. 在 main 中并没有调用 f，而是在编译期直接算出了 `f(8)+1` 的结果 12；在 f 中也并没有调用 g，而是将 g 的汇编代码直接 inline 到 f 的汇编代码中；
3. printf 的地址在 0x0648；
4. 在 main 里面通过 jalr 跳转到 printf 之后，ra 的值应该是下一条指令的地址 0x38；
5. 通过实验了解大小端序，暂时先略过；
6. 探讨 `printf("x=%d y=%d", 3)` 会有什么输出，y 应该会是一个保存在 a2 寄存器里面的奇怪的值。

## lab: backtrace

题外话：有关 RISC-V 汇编和 call convention，MIT6.004 的课件 [1](https://6004.mit.edu/web/_static/fall20/resources/sp20/L03.pdf) 和 [2](https://6004.mit.edu/web/_static/fall20/resources/sp20/L04.pdf) 讲的非常好。RISC-V 的 stackframe 布局则能够在[这里](https://pdos.csail.mit.edu/6.828/2020/lec/l-riscv-slides.pdf)找到。

题目描述：实现 backtrace 功能，在某个时间点（比如 panic 的时候）沿着一层层 stackframe 去打印其中记录的 `ra` 寄存器的值。注意每个 stackframe 可以认为从高到低包括 `ra`，上一层的 frame pointer，callee-saved registers 还有一些局部变量。当前层的 frame pointer 保存在 `s0` 寄存器中，`ra` 相对当前 fp 的偏移量是 -8，上一层的 fp 相对当前 fp 的偏移量是 -16。fp 可以理解为上一层的 stackframe 的最低地址。

实现简述：我们只要迭代打印当前 stack frame 的 `ra` 并注意边界条件即可。

备注：通过 `addr2line` 工具可以将地址转化为可执行文件里面的代码行数。这样的话我们就不必在 kernel 里面尝试解析 ELF 了。

## lab: alarm

题目描述：新增一个 `sigalarm(interval, handler)` 系统调用。当一个应用调用 `sigalarm(n, fn)` 之后，该应用每执行 `n` 个 ticks（每个 ticks 长达若干个 CPU 时钟周期），就会调用一下 `fn` 函数，在调用结束后继续回到之前的执行现场继续执行。若调用 `sigalarm(0, 0)` ，则会取消这种周期性调用机制。

如测试程序 `alarmtest.c`：

```c
//
// test program for the alarm lab.
// you can modify this file for testing,
// but please make sure your kernel
// modifications pass the original
// versions of these tests.
//

#include "kernel/param.h"
#include "kernel/types.h"
#include "kernel/stat.h"
#include "kernel/riscv.h"
#include "user/user.h"

void test0();
void test1();
void test2();
void periodic();
void slow_handler();

int
main(int argc, char *argv[])
{
  test0();
  test1();
  test2();
  exit(0);
}

volatile static int count;

void
periodic()
{
  count = count + 1;
  printf("alarm!\n");
  sigreturn();
}

// tests whether the kernel calls
// the alarm handler even a single time.
void
test0()
{
  int i;
  printf("test0 start\n");
  count = 0;
  sigalarm(2, periodic);
  for(i = 0; i < 1000*500000; i++){
    if((i % 1000000) == 0)
      write(2, ".", 1);
    if(count > 0)
      break;
  }
  sigalarm(0, 0);
  if(count > 0){
    printf("test0 passed\n");
  } else {
    printf("\ntest0 failed: the kernel never called the alarm handler\n");
  }
}

void __attribute__ ((noinline)) foo(int i, int *j) {
  if((i % 2500000) == 0) {
    write(2, ".", 1);
  }
  *j += 1;
}

//
// tests that the kernel calls the handler multiple times.
//
// tests that, when the handler returns, it returns to
// the point in the program where the timer interrupt
// occurred, with all registers holding the same values they
// held when the interrupt occurred.
//
void
test1()
{
  int i;
  int j;

  printf("test1 start\n");
  count = 0;
  j = 0;
  sigalarm(2, periodic);
  for(i = 0; i < 500000000; i++){
    if(count >= 10)
      break;
    foo(i, &j);
  }
  if(count < 10){
    printf("\ntest1 failed: too few calls to the handler\n");
  } else if(i != j){
    // the loop should have called foo() i times, and foo() should
    // have incremented j once per call, so j should equal i.
    // once possible source of errors is that the handler may
    // return somewhere other than where the timer interrupt
    // occurred; another is that that registers may not be
    // restored correctly, causing i or j or the address ofj
    // to get an incorrect value.
    printf("\ntest1 failed: foo() executed fewer times than it was called\n");
  } else {
    printf("test1 passed\n");
  }
}

//
// tests that kernel does not allow reentrant alarm calls.
void
test2()
{
  int i;
  int pid;
  int status;

  printf("test2 start\n");
  if ((pid = fork()) < 0) {
    printf("test2: fork failed\n");
  }
  if (pid == 0) {
    count = 0;
    sigalarm(2, slow_handler);
    for(i = 0; i < 1000*500000; i++){
      if((i % 1000000) == 0)
        write(2, ".", 1);
      if(count > 0)
        break;
    }
    if (count == 0) {
      printf("\ntest2 failed: alarm not called\n");
      exit(1);
    }
    exit(0);
  }
  wait(&status);
  if (status == 0) {
    printf("test2 passed\n");
  }
}

void
slow_handler()
{
  count++;
  printf("alarm!\n");
  if (count > 1) {
    printf("test2 failed: alarm handler called more than once\n");
    exit(1);
  }
  for (int i = 0; i < 1000*500000; i++) {
    asm volatile("nop"); // avoid compiler optimizing away loop
  }
  sigalarm(0, 0);
  sigreturn();
}
```

其期望输出为：

```shell
$ alarmtest
test0 start
........alarm!
test0 passed
test1 start
...alarm!
..alarm!
...alarm!
..alarm!
...alarm!
..alarm!
...alarm!
..alarm!
...alarm!
..alarm!
test1 passed
test2 start
................alarm!
test2 passed
$ usertests
...
ALL TESTS PASSED
$
```

### 单次触发

这里我们只要能够做到触发一次即可。

* 首先是要例行添加新的系统调用；
* `sys_sigalarm` 需要在 PCB 里面添加触发周期和触发函数的地址；
* PCB 里面需要增加一个新的 field 表示距离上次触发之后又已经经过了多少个 ticks；
* 在 `trap.c` 里面的 `usertrap.c` 里面本来有一个发现是时钟中断直接 `yield` 交出 CPU 使用权的地方，我们在这之前更新上面提到的 ticks 数即可；
* 注意触发函数的地址**可能为 0**，因此不能用它来作为是否触发的判定依据而要看触发周期；
* 在`usertrap.c` 里面同样的地方，在 `yield` 之前，如果发现 ticks 数目达到了触发周期，我们就需要调用触发函数。注意触发函数在用户态执行，且在末尾需要手动调用 `sys_sigreturn` 来返回到内核态。但在这里我们不考虑继续执行之前的用户代码，只需要在返回之前将 `sepc` 修改为触发函数的地址即可。

### 继续执行

* 在即将返回并执行触发函数之前，我们需要在某个地方（如 PCB 中）保存完整的 trapframe。并将 ticks 计数重置为 0。
* 随后触发函数结束，通过 `sys_sigreturn` 回到内核态的时候，我们只需将之前的 trapframe 从 PCB 中取出并替换到用户地址空间即可。这样这个系统调用返回就可以继续从之前被中断的用户代码执行了。
* 我们还需要在 PCB 中保存现在是否在执行触发函数来应对那些执行时间可能很长的触发函数。如果是的话，遇到时钟中断不应该有任何动作（这里是否 yield 应该都一样吧）。

