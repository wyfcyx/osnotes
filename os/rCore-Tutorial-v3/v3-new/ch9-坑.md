* 不能直接`jr trap_from_kernel`，暂时使用`sscratch`进行中转

* 在`read_block`的时候，还没有进入`condvar.wait`之前就打开中断使得中断不能唤醒任何任务，从而该任务永久卡死

  这个应该如何解决呢

  这需要将`condvar`封装到`upintrfreecell`中形成一个类似于`sleeplock`的结构，这样保证我们总能将进程加入到等待队列后再开启中断
  
* 另外忽然想起一个好点子是：要不要自己写spinlock/sleeplock?

  实际上并不是这个点子。而是在`upsafecell`中新增一个接收闭包的函数，这样就能在函数返回之后自动释放锁，这在很多时候会很大程度上简化代码，也会“更加Rust”。