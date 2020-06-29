# [Zircon 内核对象](https://fuchsia.dev/fuchsia-src/reference/kernel_objects/objects)

Zircon 是基于对象的内核。用户态代码几乎只能通过对象句柄（Object Handle）来与 OS 资源进行交互。一个句柄可以被认为是访问 OS 一个特定的子系统中一种特定的资源的一段被激活的会话（Session）。

目前，Zircon 管理如下资源：

* 处理器时间
* 内存与地址空间
* 设备 I/O 内存（即 MMIO）
* 中断
* 信号与等待

## 应用中的内核对象

### IPC

### Tasks

#### [进程 Process](https://fuchsia.dev/fuchsia-src/reference/kernel_objects/process)

* 进程 ：包含单个或多个线程的运行中的程序，管理若干资源

* 进程管理的资源：句柄、*VMAR*、线程

* 一般来说，直到运行的程序运行结束或者被强制退出位置，进程都与它相关

* 进程被 *Job* 所有，它允许一个含有一个或者多个进程的应用从资源和权限限制的角度被看做单个实体，比如说在生命周期控制方面

* 进程的生命周期：进程通过 `zx_process_create` 创建并通过 `zx_process_start` 开始运行，而当如下情况发生时进程停止执行：

    * 进程的最后一个线程退出或者被终止；
    * 进程调用了 `zx_process_exit` 函数；
    * 进程的父 *Job* 终止了该进程；
    * 进程的父 *Job* 被销毁

* 注意 `zx_process_create` 不能被调用两次；当一个进程的最后一个线程退出之后，不能再向着个进程中加入新的线程。

* 相关系统调用如下：
    * `zx_process_create`: 创建进程；
    * `zx_process_read_memory`: 读取一个进程的地址空间；
    * `zx_process_start`: 使一个**新进程**开始执行；
    * `zx_process_write_memory`: 写入一个进程的地址空间；
    * `zx_process_exit`: 退出当前进程；
    * <-------------------------------------------------------------------------->
    * `zx_job_create`: 在一个父 *Job* 下创建一个新 *Job*；
    * <-------------------------------------------------------------------------->
    * `zx_task_create_exception_channel`: 监听 *Task* 异常；
    * <-------------------------------------------------------------------------->
    * `zx_vmar_map`: 将内存映射到地址空间内的一段区间；
    * `zx_vmar_protect`: 修改地址空间内的一段区间的访问权限；
    * `zx_vmar_unmap`: 解映射

#### [线程 Thread](https://fuchsia.dev/fuchsia-src/reference/kernel_objects/thread)

* 线程：运行/计算单位（runnable/computation entity）

* 线程对象代表一个分时 CPU 的执行上下文，线程对象需要挂在一个特定的进程对象下面，因为它需要进程提供的内存和访问其他对象的句柄，这些对于 I/O 和进行计算是必需的

* 线程的生命周期

  * 线程通过 `zx_thread_create` 创建，但是只有当 `zx_thread_start` 或者 `zx_process_start` 被调用之后才开始执行。这些调用都需要传入一个入口点作为参数。传进 `zx_process_start` 的线程需要是对应进程上第一个开始执行的线程。

  * 线程停止执行则有以下几种方法

    1. 通过调用 `zx_thread_exit`
    2. 通过调用 `zx_vmar_unmap_handle_close_thread_exit`
    3. 通过调用 `zx_futex_wake_handle_close_thread_exit`
    4. 当父进程终止的时候
    5. 带着线程的句柄调用 `zx_task_kill`
    6. 产生了一个找不到句柄或者句柄决定终止线程执行的异常

    单纯从入口点进入后返回并不会终止线程执行，必须满足上述条件之一。

    关闭指向线程的最后一个句柄也不会终止线程执行。若想在没有句柄的情况下强制性终止一个线程，可以通过 `zx_object_get_child` 获取指向该线程的一个句柄。然而，这种做法是**强烈不推荐**的，因为它可能会损坏进程。

  * Fuchsia 原生线程一直是分离（detached）的，也就是说，不需要 `join` 操作就能干净的终止线程。然而，内核上层的运行时可能需要将线程 Join 起来，比如 C11 或 POSIX。

* 信号

  线程提供以下信号：

  * `ZX_THREAD_TERMINATED`
  * `ZX_THREAD_SUSPENDED`
  * `ZX_THREAD_RUNNING`

  它们之间可以随着线程的运行状态合理的进行转换。

  注意这些信号是以或的形式在 `zx_object_wait_*` 系列的函数维护的状态中存储的，因此当他们返回的时候你能够看到请求信号的任何组合。

* 相关系统调用

  * `zx_thread_create`: 创建线程；
  * `zx_thread_exit`: 终止线程；
  * `zx_thread_read_state`: 从线程中读取寄存器状态；
  * `zx_thread_start`: 使一个新线程开始执行；
  * `zx_thread_write_state`: 修改线程的寄存器状态；
  * <-------------------------------------------------------------------------->
  * `zx_task_create_exception_channel`: 监听 *Task* 的异常；
  * `zx_task_kill`: 使一个 *Task* 停止运行；

#### [Job](https://fuchsia.dev/fuchsia-src/reference/kernel_objects/job)

* *Job* 管理一组进程，还可能管理若干子 *Job*。*Job* 用来追踪内核中的一些特权操作（如在多种不同的设置下发起各种各样的系统调用）以及限制基本资源的使用（如 CPU、内存等）。每个进程都归一个 *Job* 所有。Fuchsia 中的所有 *Job* 构成了一棵树，除了根 *Job* 之外，每个 *Job* 都属于它的父 *Job* 所有。
* 具体而言，一个 *Job* 对象中含有以下内容：
  * 一个指向其父 *Job* 的引用；
  * 一个子 *Job* 集合，其中每个子 *Job* 的父亲都是它；
  * 一个成员进程集合；
  * 一个 *Policy* 集合（*目前暂未实现*）
* *Job* 最大的意义就是允许统一管理多个进程
* 相关系统调用：
  * `zx_job_create`: 创建一个新的子 *Job*
  * `zx_job_set_critical`: 将 *Job* 中的一个进程设置为重要的
  * `zx_job_set_policy`: 为 *Job* 中的新进程设置策略
  * `zx_process_create`: 在 *Job* 内创建一个新进程
  * `zx_task_create_exception_channel`: 监听 *Task* 的异常
  * `zx_task_kill`: 使一个 *Task* 终止执行

#### [Task](https://fuchsia.dev/docs/reference/kernel_objects/task)

* 抽象了内核对象 *Thread, Process, Job* 中运行特性的一个子类，也就是说 *Thread, Process, Job* 都是 *Task*，它们都可以被挂起、还原、杀死。
* 相关系统调用：
  * `zx_task_create_exception_channel`: 监听 *Task* 的异常；
  * `zx_task_kill`: 停止执行一个 *Task*

### 调度 Scheduling

### 信号 Signaling

### 内存与地址空间

#### [虚拟内存对象 VMO](https://fuchsia.dev/fuchsia-src/reference/kernel_objects/vm_object)

* VMO 代表一段连续的虚拟内存空间，它可以被映射到多个不同的地址空间中
* VMO 在用户态和内核态使用，既可以代表物理页帧，也可以代表虚拟页面。它们是进程间共享内存以及用户态和内核态共享内存的标准方式
* VMO 通过 `zx_vmo_create` 来创建，基本的 I/O 通过 `zx_vmo_read, zx_vmo_write` 来实现。同时，可以通过 `zx_vmo_get_size, zx_vmo_set_size` 分别来取得/修改 VMO 的大小。VMO 的大小会根据页的大小由内核进行下取整。
* 页面可以通过 `zx_vmo_read, zx_vmo_write` 按需分配给 VMO，也可以通过写入 `zx_vmar_map` 创建的 VMO 的映射。VMO 可以手动调用 `zx_vmo_op_range` 来分配/回收页面，这取决于操作类型的不同（`ZX_VMO_OP_COMMIT, ZX_VMO_OP_DECOMMIT`），但是他应当被视为一个底层操作。`zx_vmo_op_range` 还可以对一个 VMO 持有的页面进行缓存和锁等操作。
* 出于特殊目的需要特别的缓存策略的进程可以通过 `zx_vmo_set_cache_policy` 来设置一个 VMO 的缓存策略，一个典型的应用场景是设备驱动。
* 相关系统调用
  * `zx_vmo_create`: 创建一个 VMO
  * `zx_vmo_read/zx_vmo_write`: 从 VMO 中读取/写入到 VMO 中
  * `zx_vmo_get_size/zx_vmo_set_size`: 读取/修改 VMO 的大小
  * `zx_vmo_op_range`: 对于 VMO 中的一段存储区间进行某种操作
  * `zx_vmo_set_cache_policy`: 设置 VMO 持有的页面的缓存策略
  * <-------------------------------------------------------------------------->
  * `zx_vmar_map`: 将一个 VMO 映射到一个进程中
  * `zx_vmar_unmap`: 解除 VMO 和进程之间的映射

#### [虚拟内存地址区域 VMAR](https://fuchsia.dev/fuchsia-src/reference/kernel_objects/vm_address_region)

* VMAR 是虚拟内存地址空间中的一段连续区域，被用户态和内核态用来代表地址空间的分配
* 每个进程开始时都带有一个被称为 root VMAR 的 VMAR（参考 `zx_process_create`），它代表整个地址空间。每个 VMAR 可以从逻辑上被分为任意数量两两不相交的部分，其中每个部分代表一个子 VMAR，一个虚拟内存映射，或者只是代表一段间隙。子 VMAR 可以使用 `zx_vmar_allocate` 创建。虚拟内存映射可以使用 `zx_vmar_map` 创建。
* VMAR 使用一个层次化的权限模型来管理映射权限。举例来说，root VMAR 允许 RWX 映射，因此可以创建一个允许 RW 映射的它的子 VMAR，但这个 VMAR 就不能再创建一个支持 X 映射的子 VMAR。
* 当我们通过 `zx_vmar_allocate` 来创建一个 VMAR 时，它的父 VMAR 保留一个指向它的映射。正因如此，如果所有指向一个子 VMAR 的句柄都被关闭，这个孩子以及它所有的后代都将继续在地址空间中可用。若想将一个孩子从地址空间中剥离，我们必须在指向这个孩子的句柄上调用 `zx_vmar_destroy`。
* 默认设置下，地址空间的所有分配都被随机化了。在 VMAR 创建的时候，调用者可以选择它使用哪种随机化算法。默认的分配器试图将分配布满整个 VMAR 空间，而选择 `ZX_VM_COMPACT` 的替代分配器则尽可能分配更为靠近的地址，但依然收到随机化影响。默认的分配器更为推荐使用。
* VMAR 可选的支持线性映射（这里被称为 fixed-offset mapping 即 specific mapping），它主要用于创建守护页或者保证映射位置的相对关系。每个 VMAR 都可以有 `ZX_VM_CAN_MAP_SPECIFIC` 权限，它不受层次化权限模型限制。
* 相关系统调用
  * `zx_vmar_allocate`: 新建一个子 VMAR
  * `zx_vmar_map`: 将一个 VMO 映射到进程内
  * `zx_vmar_unmap`: 在进程中解映射一个内存区域
  * `zx_vmar_protect`: 调整内存访问权限
  * `zx_vmar_destroy`: 销毁一个 VMAR 以及它所有的孩子



### 等待



## 驱动中的内核对象

## 内核对象与 LK

## 内核对象的生命周期

## 分配器

## 内核对象安全性

