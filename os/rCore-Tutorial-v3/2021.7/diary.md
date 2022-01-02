# 2021年7月迭代日志

这里简要介绍一下最新一次迭代的日志。

## 0708

首先是把前面的章节进行若干更新。

ch1更新了rust版本，rustsbi新版似乎有点问题就没更新，在os/Makefile中新增了一个switch-check机制，如果更换平台的话会优先进行一次make clean，无需手动clean了。

## 0709

ch2在ch1的基础上，将AppManager的wrapper改成了自己设计的UPSafeCell，可以通过`upsafe_access`方法来访问。还直接把碍事的AppManagerInner给删掉了。另外每次`load_app`之前区域覆盖为0改成了：

```rust
core::slice::from_raw_parts_mut(
    APP_BASE_ADDRESS as *mut u8,
    APP_SIZE_LIMIT
).fill(0);
```

这么说来`clear_bss`也可以改一下。

ch3在ch2的基础上，首先将TaskManager改成基于UPSafeCell，主要是换掉了里面TaskManagerInner的wrapper。接着是由于Rust的版本更新，用户栈、内核栈还有TaskControlBlock数组的初始化需要它们分别实现Copy/Clone Trait而不能直接写一个feature了。仔细想想，这些类型我们都不会按值传参所以似乎也不会不安全。

