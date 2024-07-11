# [link](https://rust-unofficial.github.io/patterns/)

当panic的时候，rust会进行栈的unwind，此时会对栈上的对象进行drop进行资源回收，但是如果drop逻辑再次panic的话当前线程就会被abort掉，等于线程上剩下的资源也无法回收了。
