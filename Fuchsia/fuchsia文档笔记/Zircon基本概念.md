# [Zircon基本概念](https://fuchsia.dev/docs/concepts/kernel/concepts)

内核管理很多不同种类的对象，能直接通过系统调用访问是实现了分发器 (Dispatcher) 接口的 C++ 类。它们的实现放在[这里](https://fuchsia.googlesource.com/fuchsia/+/master/zircon/kernel/object)。其中很多是独立的高阶对象，也有一些是由低阶的 LK([LittleKernel](https://github.com/littlekernel/lk)) 对象包装而成的。

## 系统调用

用户态代码通过系统调用与内核对象进行交互，并且几乎都用到了句柄。在用户态，每个句柄用一个 32 位整数表示 (type `zx_handle_t`) 。当系统调用被执行时，内核首先根据在调用进程句柄表中的实际句柄检查句柄参数，随后确认该句柄有着正确的类型(例如，将一个线程句柄传给一个需要事件句柄作为输入的系统调用将导致错误)且该句柄有着足够的权限请求对应的操作。

从权限管理的角度，可以将系统调用大致分成三类：

1. 很小一部分的系统调用没有任何限制，如 `zx_clock_get, zx_nanosleep` 可以被任何线程调用；
2. 以一个句柄作为第一个参数，对应着调用所需的内核对象。这种系统调用是最多的，如 `zx_channel_write, zx_port_queue` 等；
3. 创建新的内核对象但不需要句柄作为输入的系统调用，如 `zx_event_create, zx_channel_create`。这个访问的过程被调用进程所在的任务 (Job) 所控制。

系统调用由 `libzircon.so` 提供，它是一个 Zircon 内核向用户态提供的“虚拟”共享库，应该被更准确的称为虚拟动态共享对象 (virtual Dynamic Shared Object, vDSO)。提供的接口类型是 C ELF ABI (这里不太好翻译，译者注)，函数名则形如 `zx_noun_verb` 或这 `zx_noun_verb_direct-object`。

这些系统调用以一种自定义的 FIDL(Fuchsia Interface Defination Language，这里不详细展开) 格式定义在 [//zircon/vdso](https://fuchsia.googlesource.com/fuchsia/+/master/zircon/vdso/) 中，这些定义首先被通过 `fidlc` 导出其 IR 表示，随后交给 `kazoo` 工具生成多种不同的格式并像胶水一样连接起各模块。

## 句柄和权限(暂定)

对象可能会有多个指向它的句柄(在一个或多个进程中)。

对于几乎所有的对象，当指向它的最后一个打开的句柄被关闭之后，这个对象本身也会被销毁，或者被丢到一个可能不会被撤销的终止状态中。

句柄可以通过将它们通过 `zx_channel_write` 写入通道来从一个进程移动到另外一个。或者，通过 `zx_process_start` 可以将句柄作为参数传给一个新进程的第一个线程。

在句柄或者它指向的对象上进行的动作由附属于该句柄的权限 (Right) 进行管理。指向同一个对象的两个句柄可能有着不同的权限。

`zx_handle_duplicate, zx_handle_replace` 等系统调用可以在传入一个句柄的情况下，获取指向相同对象的另一个句柄，并可选择性的减少权限。`zx_handle_close` 负责关闭句柄，并在该句柄是它指向的对象的最后一个句柄时释放该对象。相似的，`zx_handle_close_many` 关闭一个句柄序列。

## 内核对象 ID

内核中的每一个对象都有一个 koid(kernel object id)，它是一个 64 位整数，用于区分不同的对象且在系统运行的整个生命周期中是唯一的。这意味着 koid 不会被重复利用。

有两种特殊的 koid 值：

`ZX_KOID_INVALID`：值为 0 ，用作 null 的含义；

`ZX_KOID_KERNEL`：唯一的内核对应的 koid。

内核生成的 koid 仅用到 63 位(事实上这已经足够了)，这为人工分配的 koid (将最高位设置为 1 )留出了空间。内核生成的 koid 的分配顺序目前并未被明确规定且在不断发生变化。

人工分配的 koid 可以用来区分人工对象，类似追踪时的虚拟线程，由工具进行消耗。人工的 koid 应如何分配留给程序自己实现，在次文档中并不会给出任何规则或习惯。

## 任务、进程与线程

线程代表在一个它所属的进程拥有的地址空间内的执行流(寄存器、栈等)。而进程的所有者是任务 (Job)，它规定了多种资源限制。每个任务都属于它的父任务，最上层的根任务由内核在启动的时候创建并传递给[第一个用户态进程](https://fuchsia.dev/docs/concepts/booting/userboot) `userboot`。

如果没有一个任务句柄，一个线程就不能创建另一个进程或另一项任务。

在内核层之上，用户态功能与协议提供了[程序加载](https://fuchsia.dev/fuchsia-src/concepts/booting/program_loading) (program loading) 功能。

相关系统调用：`zx_process_create, zx_process_start, zx_thread_create, zx_thread_start`

## 消息传递：套接字、通道

套接字和通道都是双向、双端的 IPC 对象。创建一个套接字或通道将返回两个句柄，每个指向该对象的一端。

套接字是面向流的，数据可能以一个或多个字节为单位进行读写。可能出现短写 (short write，套接字的缓冲已满)或短读 (short read，返回的数据长度比请求的长度要小，也就是套接字当前缓冲不足)的情况。

通道是面向数据报的，其传递的信息有一个容量的最大限制 `ZX_CHANNEL_MAX_MSG_BYTES`，最多同时有 `ZX_CHANNEL_MAX_MSG_HANDLE` 个句柄属于一条消息。他们并不支持 short read/write，一条消息只有符合传输协议与不符合两种可能。

当我们将句柄写入通道时，它们将从发送进程中移除。当一条带着句柄的消息从通道中被读进来，句柄将被加入接受进程中。在这两个事件中间，相关的句柄持续存在(保证它们指向的对象也可以持续存在)，除非通道的写端被关闭，在这种情况下该写端接收到的所有消息都会被丢弃，这些消息中包含的句柄也都会被关闭。

相关系统调用：`zx_channel_create, zx_channel_read, zx_channel_write, zx_channel_call, zx_socket_create, zx_socket_read, zx_socket_write`

## 对象与信号

每个对象可能有最多 32 个信号，用 `zx_signalst` 类型表示并由 *ZXSIGNAL* 定义，每个信号代表描述对象当前状态的一段信息。举例来说，通道和套接字可以用 *READABLE* 和 *WRITABLE* 来描述，而进程或线程可以用 *TERMINATED* 表示已被终止。

一个线程可能需要等待一个或多个对象传来的信号从而进入就绪状态。

更多的内容参考[信号](https://fuchsia.dev/docs/concepts/kernel/signals)。

## 等待：等待一个、等待多个、与端口

一个线程可以使用 `zx_object_wait_one` 来等待一个句柄发来的信号变成就绪状态，`zx_object_wait_many` 可以等待多个句柄。这些调用都可以设置一个超时时间，如果期间没有收到任何信号，该调用就会直接返回。

Timeouts may deviate from the specified deadline according to timer slack. See [timer slack](https://fuchsia.dev/docs/concepts/kernel/timer_slack) for more information.(目前不太懂什么意思，译者注)

如果一个线程正在等待大量的句柄发来信号，使用端口将更为高效，他是一个特殊的对象，其他对象可以绑定到它身上，使得那些对象一旦发出信号，端口对象就会收到一个包含着信号相关信息的包。

相关系统调用：`zx_port_create, zx_port_queue, zx_port_wait, zx_port_cancel`。

## 事件与事件对

事件是一种最简单的对象，除了一个被激活的信号集合之外就没有其他状态了。

一个事件对是一对可以互相发送信号的事件组成的二元组。事件对的其中一个有用的特性是当它的一端被销毁(所有指向它的句柄都被关闭)时，它的另一端会收到一个 *PEER_CLOSED* 信号。

相关系统调用：`zx_event_create, zx_eventpair_create`。

## 共享内存：虚拟内存对象 (VMOs)

虚拟内存对象代表一个物理页帧集合，或者表示为那些将被懒惰的按需创建/填充页面预留出的位置。

它们可以通过 `zx_vmar_map` 映射到一个进程的地址空间，或者通过 `zx_vmar_unmap` 解映射。被映射的页面的访问权限可以通过 `zx_vmar_protect` 进行调整。

虚拟内存对象可以通过 `zx_vmo_read, zx_vmo_write` 直接读写。因此对于“创建一个虚拟内存对象，向里面写入一个数据集，并将其传给另一个进程使用”这种仅访问一次的操作，将它们映射到一个地址空间的开销可以忽略。

## 地址空间管理

虚拟地址区域 (Virtual Memory Address Region, VMARs) 提供了管理一个进程地址空间的抽象。当进程创建的时候，一个指向根 VMAR 的句柄被传给进程创建者。该句柄指向一个包含整个地址空间的 VMAR。该地址空间可以通过 `zx_vmar_map, zx_vmar_allocate` 进行调整。`zx_vmar_allocate` 可以用来创建被称为子区域或孩子的新的 VMAR，它们可以把地址空间的不同区域进行分组管理。

相关系统调用：`zx_vmar_map, zx_vmar_allocate, zx_vmar_protect, zx_vmar_unmap, zx_vmar_destroy`。

## Futex (Fast Userspace Mutex)

Futex 是内核提供的原语，常与用户态的原子操作一并使用来实现高效的同步互斥原语。通常只有标准库的实现者才会对他们感兴趣。Zircon 的 libc 和 libc++ 为 Mutex、条件变量原语等提供了 C11, C++, 和 pthread 接口，都是基于 Futex 来实现的。

相关系统调用：`zx_futex_wait, zx_futex_wake, zx_futex_requeue`。