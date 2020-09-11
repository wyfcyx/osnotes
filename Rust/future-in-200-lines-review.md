这里重新整理一下[整个的代码](https://cfsamson.github.io/books-futures-explained/8_finished_example.html)，再重新理解一下。

## Parker

首先是 `Parker`，在 Crossbeam 里面能找到类似的工具，功能类似 `thread::park/unpark` ，可以暂停/继续线程。但是目前我还不知道为什么不能用 `thread::park/unpark`。我们自己实现一个 `Parker`，如下：

```rust
// 每个 thread 中会保存一个 Parker 实例
// 用 Mutex 保护一个 bool 值 resumable，如果是 true 的话可以继续运行
// CondVar 则是对一个 MutexGuard 进行 wait，返回一个 wrap 了这个 MutexGuard 的 LockResult
#[derive(Default)]
struct Parker(Mutex<bool>, Condvar);

impl Parker {
    // 一个 thread 可以通过 Parker::park 阻塞自身
    fn park(&self) {
        // 获取 resumable 的 MutexGuard
        let mut resumable = self.0.lock().unwrap();
        // 若 resumable=false 进入循环
        while !*resumable {
            // 结构体内部的 CondVar wait 这个 MutexGuard
            // 阻塞当前线程，在被唤醒的时候，将会返回一个包裹了
            // 传进去的 MutexGuard 的 wrapper，将所有权
            // 转移回来。
            resumable = self.1.wait(resumable).unwrap();
            // 在唤醒它的时候，且在所有权转移回来之前，
            // 会将 resumable 设置为 true
            // 于是会在判断的时候退出 while 循环
        }
        // 退出循环之后，将 resumable 设置为 false
        // 使得下次调用 park 的时候可以直接进入循环体
        // 阻塞当前线程。
        *resumable = false;
    }

    // 其他 thread 可以通过调用某个 thread 的 Parker::unpark 唤醒它
    fn unpark(&self) {
        // 将那个线程的 Parker::resumable 设置为 true
        // 使得它被唤醒后可以退出 park 循环
        *self.0.lock().unwrap() = true;
        // 唤醒那个线程
        self.1.notify_one();
    }
}
```

我们大概知道 `Parker` 每个线程里面都有一个。

## Waker

我们可以通过 `core::task::{Context,Waker,RawWaker,RawWakerVTable}` 来将我们自己的 `Waker` 实现包装起来。

比如这是我们自己实现的 `MyWaker`：

```rust
#[derive(Clone)]
struct MyWaker {
    parker: Arc<Parker>,
}
```

我们需要给它实现两个功能。

第一个是通过它进行唤醒：

```rust
fn mywaker_wake(s: &MyWaker) {
    let waker_arc = unsafe { Arc::from_raw(s) };
    waker_arc.parker.unpark();
}
```

第二是对它进行复制：

```rust
fn mywaker_clone(s: &MyWaker) -> RawWaker {
    let arc = unsafe { Arc::from_raw(s) };
    // 当一个变量生命周期结束后，它会被 drop，而且它本身会被 invalidate
    // 而 std::mem::forget 仅 invalidate 变量，却不会 drop 它。
    // 因此，这行代码的意思是将 s 的引用计数 + 1
    std::mem::forget(arc.clone()); // increase ref count
    // 通过 RawWaker::new 构造一个新的 RawWaker
    // RawWaker::new(data: *const (), vtable: &'static RawWakerVTable) -> RawWaker
    // 和构造 trait object 的做法类似，分别处理数据指针和虚表指针
    // 但是由于它已经进行了很好的封装，这个比手动构造 trait object 要简单
    RawWaker::new(Arc::into_raw(arc) as *const (), &VTABLE)
}
```

这里的虚表 `VTABLE: &'static RawWakerVTable` 是我们用 `mywaker_clone/mywaker_wake` 两函数一起构造出来的。

```rust
const VTABLE: RawWakerVTable = unsafe {
    // 这里我们需要构造四个闭包，输入参数类型都是 *const ()，含义不一
    // 四个闭包分别表示 clone/wake/wake_ref/decrease refcount
    RawWakerVTable::new(
        // 输入参数含义为指向我们的 Waker 的 raw pointer
        // 因此 &*(s as *const MyWaker) 就是 &MyWaker
        |s| mywaker_clone(&*(s as *const MyWaker)),   // clone
        // 与上面一个同理
        |s| mywaker_wake(&*(s as *const MyWaker)),    // wake
        // 输入参数含义为指向我们的 &Waker 的 raw pointer
        // 因此 s as *const &MyWaker 是一个 *const &MyWaker
        // 再解引用就变成 &MyWaker
        |s| mywaker_wake(*(s as *const &MyWaker)),    // wake by ref
        // 输入参数含义同样为指向 Waker 的 raw pointer
        // Arc::from_raw(*const T) -> Arc<T>
        // 我们将其 drop 掉即可减少 Waker 的引用计数
        |s| drop(Arc::from_raw(s as *const MyWaker)), // decrease refcount
    )
};
```

目前我们讨论的都是我们自定义并要实现特定唤醒功能的 `MyWaker` 到 `RawWaker` 的封装，这依赖于为 `MyWaker` 实现的 `wake/clone` 功能。我们还要进一步将 `RawWaker` 包装成一个 `Waker`。

```rust
fn mywaker_into_waker(s: *const MyWaker) -> Waker {
    // 将 MyWaker 包装成一个 RawWaker
    let raw_waker = RawWaker::new(s as *const (), &VTABLE);
    // 将 RawWaker 包装成一个 Waker
    unsafe { Waker::from_raw(raw_waker) }
}
```

看起来，最终的 `Waker` 对应于我们手动构造的那个 trait object，由于 `Waker` 自身需要多次调用虚表中的 `wake/wake_ref/clone/dec_refcount`，那么实际上我们要维护引用计数的是 `Waker` 的 data 部分也就是 `MyWaker`，在 `clone/dec_refcount` 实现中我们需要对 `MyWaker` 的 `Arc` 引用计数进行管理。

由于这并不是 `Arc` 的常规用法，因此对于引用计数的管理比较奇怪。

比如，虚表中的 `clone` 函数的类型是 `unsafe fn (_: *const ()) -> RawWaker`。最主要的问题是 `RawWaker` 仅保存 `MyWaker` 的 raw pointer，我们在 `clone` 里面可能搞出了一个 `Arc<RawWaker>` 但无处安放，在函数结束之后会被释放，引用计数还是没有改变。因此我们只能强行用 `std::mem::forget` 禁止它的 drop，这样引用即使才能增加。虚表中的 `drop` 函数也是一样，我们还是要搞出一个 `Arc<RawWaker>`，然后把它 drop 掉，就能达到减少引用计数的效果。

总结一下，我们需要实现自己的 `MyWaker` ，它的核心方法是 `wake`。也就是要唤醒什么东西的时候，我们会调用 `MyWaker::wake`。但是 Executor 和 Reactor 之间的标准接口类是 `Waker`，我们需要将 `MyWaker` 通过工具类 `RawWaker/RawWakerVTable` 封装成一个 `Waker`。

## Executor

有了运行时两个部分通信的桥梁 `Waker` 之后，我们先来看看调度器 Executor 是如何实现的。

这里我们首先要提及一个无论在运行时中的 Executor 与 Reactor，还是我们具体编写异步代码时候都需要用到的一个核心 Trait：那就是 `Future`。

`Future` 的原型定义非常简单，只需要为它实现一个 `poll` 函数：

```rust
fn poll(self: Pin<&mut Self>, cx: &mut Context) -> Poll<Self::Output>;
```

其中 `Future` 需要包裹在 `Pin` 里面，使它的本体固定在栈或者堆上不允许移动；而 `Context` 目前只是 `Waker` 的一层 wrapper。其返回值 `Poll` 是一个枚举类型：

```rust
pub enum Poll<T> {
    Ready(T),
    Pending,
}
```

在我们的例子里面 `Executor` 只有一个 `block_on` 函数：

```rust
// 执行一个 Future 并返回它的结果
fn block_on<F: Future>(mut future: F) -> F::Output {
    // 新建一个 parker
    let parker = Arc::new(Parker::default());
    // 将 parker 复制一份用来生成一个 MyWaker
    let mywaker = Arc::new(MyWaker { parker: parker.clone() });
    // 将 MyWaker 通过工具类 RawWaker/RawWakerVTable 包装成一个 Waker
    let waker = mywaker_into_waker(Arc::into_raw(mywaker));
    // 将 Waker 进一步包装成一个 Context
    let mut cx = Context::from_waker(&waker);
    
    // 将传进来的 future 屏蔽（出于安全性），并固定到栈上
    let mut future = unsafe { Pin::new_unchecked(&mut future) };
    // Executor 这里的实现非常简单，就是一个循环
    loop {
        // 尝试 poll 一下当前的 future 看看结果如何
        match Future::poll(future.as_mut(), &mut cx) {
            // 如果 Future 已经结束的话，这里也退出循环并返回
            Poll::Ready(val) => break val,
            // 如果 Future 被阻塞，我们也没有其他 Future 去调度，将 Executor 线程阻塞
            Poll::Pending => parker.park(),
        };
    }
}
```

总结一下，这里的 Executor 在初始化阶段将 `Parker` 和 `MyWaker` 包装成一个 `Context`，作为传给 `Future::poll` 的第二个参数；而传进来的 `future` 则是被屏蔽并被包裹上一层 `Pin`，固定在内存中来保持自引用结构的性质。（按我目前的理解，其实不用 Pin，只要实现了自引用结构就可以跨暂停点进行变量借用了，但是常常会出现一些情况破坏他的自引用结构性质，故而用 Pin 来把它封装一下）。

随后，Executor 线程，也就是主线程要做的事情非常简单：就是不断 `poll` 传进来的那个 future，如果发现它在 `Pending` 就把自己这个主线程阻塞掉。看起来好像挺奇怪的；如果不是的话说明 well done 了，直接返回即可。

## Reactor

`Reactor` 接收并处理外部的事件，并据此得知哪些叶子 Future 准备好了，此时它要做的事情是找到 `Context` 里面层层包裹的 `MyWaker` 并调用 `wake` 函数。这一般来说会让 `Executor` 重新将它放回就绪队列，并在可能的时机重新 `poll` 它。那时，由于它已经 `Ready`，`Executor` 就可能会触发一系列的链式反应，将某些因它而阻塞的 `Future` 也加回就绪队列。

一般来说应当如此，但是这里的 `Reactor` 和 `Executor` 实现都异常简单——

```rust
// Reactor 支持的事件类型
// Close 表示关闭 Reactor 线程
// Timeout 表示某个任务对应的计时器超时
#[derive(Debug)]
enum Event {
    Close,
    Timeout(u64, usize),
}
// 在 Reactor 中保存的任务当前状态
// 注意，当 NotReady 的时候，Waker 的一个计数引用也被传进去
enum TaskState {
    Ready,
    NotReady(Waker),
    Finished,
}
struct Reactor {
    dispatcher: Sender<Event>,
    handle: Option<JoinHandle<()>>,
    tasks: HashMap<usize, TaskState>,
}
impl Reactor {
    // 新建一个 Reactor
    // Box: 我们希望将数据放在堆上，避免受到 new 的生命周期限制；
    // Mutex: 提供同步互斥；
    // Arc: 有多所有权需求。
    fn new() -> Arc<Mutex<Box<Self>>> {
        // 新建一条信道
        // 发送端被 Reactor 持有
        // 接收端被 Reactor 线程持有
        let (tx, rx) = channel::<Event>();
        let reactor = Arc::new(Mutex::new(Box::new(Reactor {
            dispatcher: tx,
            handle: None,
            tasks: HashMap::new(),
        })));
        
        // 得到一个 Weak<Mutex<Box<Reactor>>>
        let reactor_clone = Arc::downgrade(&reactor);
        // 新建一个 Reactor 线程，并将句柄 bind 到 handle 变量上
        let handle = thread::spawn(move || {
            let mut handles = vec![];
            // 循环读取信道输入端的事件
            for event in rx {
                let reactor = reactor_clone.clone();
                match event {
                    // 若是 Close 事件，则 break 掉循环退出线程
                    Event::Close => break,
                    // 否则说明某个计时器超时，且我们知道它的任务 ID 和计时时长
                    Event::Timeout(duration, id) => {
                        // 新建一个计时线程，并将句柄 bind 到 event_handle 变量
                        let event_handle = thread::spawn(move || {
                            // 休眠一段时间
                            thread::sleep(Duration::from_secs(duration));
                            let reactor = reactor.upgrade().unwrap();
                            // 找到多层 wrappers 里面的实际 Reactor，并调用 wake(id)
                            reactor.lock().map(|mut r| r.wake(id)).unwrap();
                        });
                        // handles 保存所有的事件句柄
                        handles.push(event_handle);
                    }
                }
            }
            // 循环退出后，我们也需要保证所有的计时器线程退出。感觉没啥用？
            handles.into_iter().for_each(|handle| handle.join().unwrap());
        });
        // 将 Reactor 线程的句柄保存在 Reactor 实例中并返回
        reactor.lock().map(|mut r| r.handle = Some(handle)).unwrap();
        reactor
    }

    // 目前只会在某个计时器超时的时候在计时器线程调用它的 wake(id)
    fn wake(&mut self, id: usize) {
        // 获取该任务当前的状态
        let state = self.tasks.get_mut(&id).unwrap();
        // 将该任务在 Reactor 的状态修改为 TaskState::Ready，并根据修改之前的状态：
        match mem::replace(state, TaskState::Ready) {
            // 如果之前没有准备好的话，现在可准备好了，直接调用里面保存的 waker.wake 就行了
            TaskState::NotReady(waker) => waker.wake(),
            // 错误情况
            TaskState::Finished => panic!("Called 'wake' twice on task: {}", id),
            _ => unreachable!()
        }
    }

    // 在 Reactor 中注册一个任务
    fn register(&mut self, duration: u64, waker: Waker, id: usize) {
        // 不允许出现相同的任务 ID
        if self.tasks.insert(id, TaskState::NotReady(waker)).is_some() {
            panic!("Tried to insert a task with id: '{}', twice!", id);
        }
        // 向信道发送端发送一个 Timeout 事件
        self.dispatcher.send(Event::Timeout(duration, id)).unwrap();
    }

    // 简单判定一个任务是否 Ready
    fn is_ready(&self, id: usize) -> bool {
        self.tasks.get(&id).map(|state| match state {
            TaskState::Ready => true,
            _ => false,
        }).unwrap_or(false)
    }
}

// 当 Reactor 实例被 drop 的时候，会向 Reactor 线程发送一个 Close 事件
// 并等待 Reactor 线程自身退出。
impl Drop for Reactor {
    fn drop(&mut self) {
        self.dispatcher.send(Event::Close).unwrap();
        self.handle.take().map(|h| h.join().unwrap()).unwrap();
    }
}
```

总结一下，`Reactor` 负责接收事件并对于适当的 `Future` 调用 `Waker.wake`；而 `Waker.wake` 实现往往要交给调度器 `Executor`，这也就是二者协作的方式了。

后面会看到 `Reactor` 实例位于主线程。当我们调用 `register` 函数的时候，就会将 `Waker` 放在任务的状态结构体中，同时发送端 `dispatcher` 就会往 Reactor 线程发送一个 Timeout 事件。Reactor 会循环接收事件，当他接收到一个 Timeout 事件时，它会新建一个计时器线程，并在计时结束之后调用 `Reactor::wake`。在 `Reactor::wake` 再去查任务状态表，找到其中的 `Waker`，并调用 `Waker::wake`。

我们知道，`Waker::wake` 的作用无非就是唤醒 Executor 线程，再尝试去 `poll` 一下传进来的 future。

## Future

我们需要编写一个实现 `Future` trait 的结构体代表我们实际上要进行的异步任务。

```rust
// Task 代表一个异步任务，我们需要为它实现 Future trait
#[derive(Clone)]
pub struct Task {
    // 任务 ID
    id: usize,
    // Reactor 的智能指针
    reactor: Arc<Mutex<Box<Reactor>>>,
    // 计时时长
    data: u64,
}
impl Task {
    fn new(reactor: Arc<Mutex<Box<Reactor>>>, data: u64, id: usize) -> Self {
        Task { id, reactor, data }
    }
}
impl Future for Task {
    type Output = usize;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        let mut r = self.reactor.lock().unwrap();
        // 如果该任务在 Reactor 中的状态为 TaskState::Ready
        if r.is_ready(self.id) {
            // 修改为 TaskState::Finished
            *r.tasks.get_mut(&self.id).unwrap() = TaskState::Finished;
            // 并返回结果
            Poll::Ready(self.id)
        // 否则，如果该任务被注册过
        } else if r.tasks.contains_key(&self.id) {
            // 我们需要更新 Reactor 中所保存的该任务对应的 Waker
            r.tasks.insert(self.id, TaskState::NotReady(cx.waker().clone()));
            // 依旧 Pending
            Poll::Pending
        } else {
            // 该任务没有在 Reactor 中注册过
            // 调用 Reactor::register 进行注册，插入任务状态表，
            // 并向 Reactor 线程发送 Timeout 事件
            r.register(self.data, cx.waker().clone(), self.id);
            // 返回 Pending
            Poll::Pending
        }
    }
}
```

`Future` 这里所做的事情主要是在和 `Reactor` 打交道。当 `poll` 一个 `Future` 的时候，我们需要到 `Reactor` 的任务状态表中去查询它的状态：如果它已经 `Ready` 的话 `poll` 就直接返回；否则之前在任务状态表中注册过的话，我们可能需要将传进来的 `Context` 更新一下；再否则我们需要将该任务在 `Reactor` 中注册一下。

## main

```rust
fn main() {
    let start = Instant::now();
    // 由此可见，Reactor 实例位于主线程
    let reactor = Reactor::new();

    // 这生成了一个 Future，等待 1 秒钟之后输出当前时间
    let fut1 = async {
        let val = Task::new(reactor.clone(), 1, 1).await;
        println!("Got {} at time: {:.2}.", val, start.elapsed().as_secs_f32());
    };

    // 这生成了一个 Future，等待 2 秒钟之后输出当前时间
    let fut2 = async {
        let val = Task::new(reactor.clone(), 2, 2).await;
        println!("Got {} at time: {:.2}.", val, start.elapsed().as_secs_f32());
    };

    // 将 fut1 和 fut2 chain 在一起形成一个新 Future
    let mainfut = async {
        fut1.await;
        fut2.await;
    };

    // 阻塞主线程直到 mainfut 返回
    block_on(mainfut);
}
```

总体看一下主线程是在做什么事情：我们将两个 `Task` 型叶子 `Future` 分别加上一行打印语句包装成两个通用 `Future`，随后将两个 `Future` chain 到一起组成 `mainfut`。那么这些 `Future` 究竟是如何组合的呢？我们不去深入其状态机的构造细节，我们在 `block_on` 中每次 `poll` 的结果为 `Pending` 之前加上一行输出，可以看到结果是：

```rust
blocked on block_on!
Got 1 at time: 1.00.
blocked on block_on!
Got 2 at time: 3.00.
```

这说明最后构成的 `mainfut` 看起来更像是一个单独的、内部不含任何嵌套子 `Future` 的 `Future`。

当我们在 `block_on` 里面 `poll` 传进去的 `mainfut` 的时候，首先它会遇到第一个计时器的 `await`，这意味着它要 `poll` 该计时器任务，由于它是一个 `Task`，因此会调用 `Task::poll`，查询 `Reactor`，发现之前没有被注册过，于是它注册并返回 `Pending`。这将会导致对于 `mainfut` 的 `poll` 也返回 `Pending`。于是 Executor 所在的主线程被休眠。

直到第一个计时器超时，它会调用 `Reactor::wake`，并将对应任务在 `Reactor` 中的状态进行修改，随即调用对应任务的 `Waker::wake`，这会唤醒主线程。那么它继续 `poll` 主 Future `mainfut`。某种机制保证它会继续 `poll` 第一个计时器对应的任务。但是现在人家查 `Reactor` 的任务状态表发现已经完成了！于是对于 `fut1` 的 poll 成功返回。输出一行语句之后发现再次遇到了一个 `await`。这个时候从状态机的角度看应该无论如何再 `poll` 一次试试。这时就和上一个计时器的情况一样了。

由于 `mainfut` 是顺序的两个 `await` ，这导致运行所需总时间是三秒而不是两秒。因为第一个计时结束之后，第二个才会被 poll，那时它才会在 `Reactor` 中注册，并启动计时线程。如果我们的 Executor 更加强大的话，完全可以将两个计时器并列。此时运行所需总时间就是两秒了。

## 总结

细数一下 Rust 提供给我们的支持：

首先是 `Future` trait。通常我们需要将一个异步任务包装成一个结构体，并为其实现 `Future` trait。这样的 `Future` 一般都是叶子 `Future`。因为，Rust 通过 `async/await` 关键字帮助我们将叶子 `Future` 以各种方式组合成多种多样的非叶 `Future`，并使用复杂的状态机来描述它们。

`Future` trait 需要实现的核心方法是 `poll`，即尝试将这个 `Future` 向下执行直到被阻塞。对于一个叶子 `Future` 而言，由于它一般与某个真实的 I/O 资源上的某些操作相对应，对它的 `poll` 不是那么简单，我们稍后再说；对于非叶 `Future` 来说，它终究可以看成若干个叶子 `Future` 的组合拼装，所以它的每一次 `poll`，都大致是某个叶子 `Future` 完成了，它可以继续占用 CPU 执行一段代码，然后又遇到了某个叶子 `Future` 被阻塞。幸运的是，使用状态机来将叶子 `Future` 组合成非叶 `Future` ，以及非叶 `Future` 的 `poll` 如何实现这两点，通过 `async/await` 关键字，Rust 已经帮我们做好了，我们无须考虑。

于是，重头戏就变成了如何实现叶子 `Future` 的 `poll`。通常来讲，第一次 `poll` 的时候，返回的结果都会是 `Pending`，可想而知在接下来的一段时间之内都没有必要再 `poll` 它，因为相应的 I/O 操作尚未结束。但是又需要有一种机制当 I/O 操作完成的时候，能够将该叶子 `Future` 重新变成可以 `poll` 的状态。这一整套机制被称为 `Future` 运行时，由两部分组成：`Executor` 和 `Reactor`。

`Executor` 是一个调度器，它相当于一个就绪队列和一个休眠队列，它可以从就绪队列中选出一个 `Future` 来 `poll`，如果它返回了 `Pending` 就将其丢进休眠队列暂时不会再 `poll` 它。可以想象的是，它的实现复杂性完全是和它支持的叶子 `Future` 组合拼接的灵活性挂钩的。而 `Reactor` 是一个唤醒器，它接受外部的事件（比如一次 I/O 操作结束），找出该操作对应的叶子 `Future`，并在 `Executor` 中唤醒它，唤醒对应的 `Future` 之后，它就又可以被 `Executor` 来 `poll` 了。

`Executor` 和 `Reactor` 之间协作的接口 `Waker` 是由 Rust 提供的。一般而言，由 `Reactor` 来调用 `Waker::wake` 来唤醒叶子 `Future`，而它的实现自然是依赖于 `Executor` 的。因此，从架构上来讲，`Executor` 应该在最底层，`Waker` 是利用 `Executor` 实现的中间层，而 `Reactor` 属于 `Waker` 的调用层。这里稍微补充一点细节，我们通常需要自己实现一个类似于 `MyWaker` 的东西，在里面实现 `wake` 函数，并将其通过 Rust 提供的工具类 `RawWaker,RawWakerVTable` 包装成一个 `Waker`，而明面上使用的也并不是 `Waker`，而是将 `Waker` 再次包装了一层变成一个 `Context`。

因此，Rust 提供给我们 `Future` trait，`async/await` 对于非叶 `Future` 的组合封装、状态机构造与 `poll` 实现，以及工具类 `RawWaker/RawWakerVTable` 帮助我们将自己的 `Waker` 包装成 `Context<Waker>`。我们只需将自定义的异步任务作为叶子 `Future` 实现它的 `poll` 方法，这又需要在 `Future` 运行时下层的 `Executor` 和运行时上层的 `Reactor` 分别提供支持。这里的上下层是从实现架构的角度来讨论的。