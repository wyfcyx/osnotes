# [Futex资料](https://www.akkadia.org/drepper/futex.pdf)

futex的系统调用接口如下：

```c
long sys_futex(void *addr1, int op,
  int val1, struct timespec *timeout,
  void *addr2, int val3
);
```

其中`addr1`指向一个完全被用户态控制的4字节的值，也就是一个futex对象。它可以是内存中的任意对齐到`sizeof(int)`的位置，但不能与DMA之类的东西有关。两个进程的`addr1`虚拟地址完全有可能实际映射到同一个物理地址，如此便可进行进程同步。

通过`op`参数可以决定对于futex对象进行何种操作：

* **FUTEX_WAIT**

  让当前线程在内核中暂停直到收到通知。如果正常暂停（并收到通知继续）的话将会返回0。

  然而如果futex的值与`val1`不同，将不会暂停而是立即返回`EWOULDBLOCK`。

  如果参数`timeout`不为`NULL`的话，线程仅会暂停一段有限的时间，由`timeout`指定，单位为秒。如果时间耗尽为止都未收到通知，则会继续并返回`ETIMEOUT`。

  如果当前线程收到信号系统调用也会返回，这种情况下返回值为`EINTR`。

  冗余参数：`addr2`

* **FUTEX_WAKE**

  可以唤醒一个或多个线程，仅需`addr1/op/val1`三个参数。其中`val1`表示唤醒线程的数目，通常仅会用到1或者**INT_MAX**，因为用户态很难获知线程的执行情况。

  内核并不会从遍历等待队列找到优先级最高的线程，正常情况下的futex并不支持实时。

  被唤醒的线程是否立即执行、唤醒者是否能够继续执行均属于实现细节，对它的行为我们无法做任何假设。特别是在多核环境下被唤醒的线程可能比唤醒者更先返回用户态。

  返回值是被唤醒的线程的数目。

* **FUTEX_WAKE_OP**

* **FUTEX_CMP_REQUEUE**

* **FUTEX_REQUEUE**

* **FUTEX_FD**