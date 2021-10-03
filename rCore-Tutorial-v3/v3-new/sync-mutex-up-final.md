Try to practice my English writing...

Now we can start to implement the final chapter.

## stage1

**target: support previous applications, but now the unit of scheduling is thread instead of process**

Firstly, `Pid` and `KernelStack` should be handled independently.

It took me some time to set up my developing environment... Now I'm using vim with a great auto completion supported by `rust-analyzer`, I did not know why it didn't work on Visual Studio Code. That was weird. Now we can move on.

Next, maybe we should create a struct storing the information of a thread. We called it `TaskControlBlock`, which is still a unit of scheduling.

***very important issue***: Now every thread needs its own `TrapContext` since multiple threads may want to enter the kernel mode at a time. This can eliminate the date races.

> Differences and connections between processes and threads
>
> * The first thread in a process is called main thread. When the main thread exits, all the other threads also exit although they are running at this time.
> * Every thread has a exit code which can be collected by other threads through something like a `ThreadHandle`. The process's exit code is equal to its main thread's exit code.
> * `fork` can be called if and only if the current process has only one thread, i.e. its main thread.
> * There're no parent or child threads. Maybe it is more like a master-slave relationship.

`ProcessControlBlock` no longer needs a full `TaskStatus`, it only needs a flag `is_zombie`.

cross reference: Every `TaskControlBlock` holds an `Arc<ProcessControlBlock>`, and every `ProcessControlBlock` holds a list of `Weak<TaskControlBlock>`。

changes in address space distribution:

* kernel space: now every process has multiple kernel stacks(1 per thread), so kernel stack should be allocated individually
* application space: maybe user stacks grow up, and `TrapContext` grow down. I think trampoline part can be shared since they are a part of a code section which is RO. Just like before, there should be guard pages between them.

`MemorySet::from_elf` won't insert `MemoryArea` used for user stack and `TrapContext`. Instead, they should be inserted into application address space when a new thread is created. In order to better manage the resources, maybe every thread holds a `ThreadResources` containing user stack and `TrapContext`, and it should be managed by `ThreadResourcesManager` which is inside the `ProcessControlBlock`. Now, the 2nd returned value of `MemorySet::from_elf` should be a base address of the user stacks in the application address space(i.e. previous `user_stack_bottom` before considering the guard page).

`task/pid.rs` -> `task/id.rs`，managing pid/tid/ustack/kstack/trap_cx. Added `TaskUserRes`, and `impl Drop`. In `TaskUserRes::drop`, the `TrapContext` of current task should be deallocated.

Now I'm editing `ProcessControlBlock::new`.

---

update from 28/09/21

fork is difficult...What should I do during fork? We allocate trap_cx and ustack during `TaskUserRes::new`, however when we are forking using `ProcessControlBlock::fork`,  it calls `MemorySet::from_existed_user`, in which trap_cx and ustack are also allocated. By the way, we don't need to consider trampoline since it's only signed in the page table, there isn't a `MapArea` related to it. But at the beginning of `MemorySet::from_existed_user`, we still need to call `MemorySet::map_trampoline`, don't forget it.

Now we don't allocate user resources automatically during `TaskUserRes::new`, it is done only if the argument called `alloc_user_res` is true(`PCB::new`). However, it is false when `PCB::fork` since they are allocated through `MemorySet::from_existed_user` which clones the whole address space including trap_cx and ustack.

Now `PCB::fork` is done! Just have a rest then...

---

update from 29/09/21

Processes manage threads, or threads manage processes? The answer is that threads hold a `Weak` of processes, and processes hold an `Arc` of threads. This is because we want the processes to be the manager of its threads.

## stage2

We'll add some new syscalls:

* `uint64 thread_create(void* entry)`

  mention that the `entry` in this syscall interface is the address of a wrapped implemented in the user library, and the user library provide another `thread_create` whose `entry` argument refers to the address of a function implements by the user library users. Return the tid of the new created thread.

* `int32 thread_wait(uint64 tid)`

  block current thread until a thread whose tid is equal to the `tid` given in the argument exits. This syscall will also return the exiting thread's exit code.

* `uint64 gettid()`

  return tid of current thread.



