## Fuchsia & Zircon 整体结构

### Zircon 特点

* 实用主义，偏微内核
* C++，支持 x86_64/ARM64
* 功能划分到内核对象
* **默认所有进程间均互相隔离**：使用 Capability 权限管理
* 安全：强制地址随机化(zCore 目前不支持)，vDSO 隔离系统调用
* user process -> vDSO -> syscall -> handles(job) in process ko

## Zircon 内核对象

* 任务
* 内存：VMAR, VMO, Pager, Strean
* IPC
* 信号
* 驱动

## Zircon/zCore 内核对象实现

## zCore 系统调用实现

## zCore 用户线程生命周期

