`futex`持续阻塞一个线程/进程，只要进程地址空间中的`uaddr`处的值还等于线程提供的`expected`。

`futex`可以用来加速纯用户态实现的自旋锁：当一个线程发现锁已经被其他线程占用时，可以使用`futex`系统调用阻塞自身直到锁标记被修改（意味着之前持有锁的线程已经释放了锁），之后线程被唤醒继续参与锁竞争，避免了CPU资源浪费。注意释放锁的线程也需要进行`futex`操作唤醒阻塞在这上面的线程。

参数：`uaddr`为进程地址空间中的地址（注意`futex word`需要为4字节且对齐到4字节）；`futex_op`为操作类型，固定的需要有一个值`val`，而`timeout,uaddr2,val3`为可选参数。`timeout`参数可以作为超时参数，为一个`timespec`指针的地址；也可以被转换成`unsigned long`，再转换成`uint32_t`，作为一个`val2`使用。

---

futex机制的优先级继承

futex接口存在优先级继承（PI）版本来防止优先级反转问题。优先级反转问题是说：一个高优先级任务阻塞在一把被一个低优先级任务持有的锁，但是系统中还存在一个中等优先级的任务，使得低优先级任务持续被抢占。于是低优先级任务无法继续执行并释放锁，而高优先级任务持续被阻塞。

优先级继承是说当高优先级任务被低优先级任务持有的锁阻塞的时候，低优先级任务被暂时提升到高优先级。为了更加有效，这种机制需要是传递性的，如果这个低优先级任务也被阻塞，那么这一条阻塞链上的任务都需要被提升到高优先级。