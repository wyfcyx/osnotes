important measurement: throughput/tail latency/security especially on data centers; custom OS images which provides self-defined scheduling policies, but cannot at an application granularity, thus limited; ghOSt delegates scheduling to user-space processes, many different mechanisms, scheduling policies can be flexible and expressive; all languages are supported, host do not need to reboot;

## I. Introduction

several scheduler examples; in kernel, it is hard to implement a scheduler: cannot achieve high performance for all cases, sometimes disruptive since it is in kernel(trade-off between complexity and availability), hard to upgrade it; disadvantages of pervious user-space solutions: change application impl significantly, require dedicated resources, or modify the kernel only for the app;

*target1*: explore how kernel should change if kernel ABI is still stable

*target2*:hardware is complex today and scheduling abstraction model is relatively simple; for example, new features: NUMA/SMP/SMT/heterogeneous computing; monolithic kernel is too simple as well

ghOSt: for native OS threads; delegates scheduling policy to user-space; "decouples kernel scheduling mechanism(in kernel, rarely changes) from policy definition(resides in apps, rapidly changes)"; arch of ghOSt: 

## II. Background & Design goals

requests for new scheduling policies which can suit for complex hardware and can protect them from microarchitectural vulnerabilities especially on the cloud

*Linux Schedulers*: scheduling class -> priority & preemptive; developers can implement their own scheduling policies for their workloads, but that is too difficult, so they tend to use existing schedulers such as CFS; in a word, for Linux, generic over performance

*Hard to develop schedulers in Linux*: written in C/assembly, no available libraries; no debug tools; can involve synchronization primitives of kernel; Linux does not accept non-generic scheduler patches, so they are maintained out-of-tree

*Even more harder to deploy schedulers*: new kernel image, thus difficult for cloud providers; it always costs several months since there is too much work to do, schedulers themselves are just the beginning;

*User-level threading is not enough*: user level scheduling schedules user threads(just multiplex M user threads on N native threads), cannot determine a user thread will run on which CPU, sometime leads to a deadlock; but ghOSt schedulers kernel threads even if it runs in user-space; solution1: 1 CPU->1 native thread, inefficient; ghOSt can both **control response time** and **share CPU resource flexibly**

*Previous schedulers only fit into specific workloads/NICs*

*Background about BPF*: (BPF, Berkeley Packet Filter, and eBPF, extended BPF which fits into modern ISAs allow user applications to provide some programs to be run in kernel, a kind of callback?)BPF's expressiveness is limited if it is used as a scheduler, and BPF runs synchronously, so it is used to guarantee some real-time constraints in some critical sections. Oppositely, most of the time, ghOSt scheduler runs async since it can have a wider perspective.

*Design goals*:

1. easy to implement and test
2. can be efficient in terms of any measurements for any workloads
3. support centralized models instead of only per-CPU models(Linux native, classical, such as CFS)
4. concurrency of scheduling policies themselves
5. fault isolation, non-disruptive updates(do not need to restart the machine of reinstall the images)

## III. Design

enclave for each scheduling policy-> several CPUs, including one or many user-space agents which decides and reports to the kernel

kernel-side: a scheduling-like class

agent: schedule native threads to hardware threads; written in any language; if crash->switch back to default scheduler, **crash resilience**, accelerate development; each agent: a `pthread`; all agents are in the same address space;

kernel-to-agent: threads states, through messages and status words which can help agents decide

> * share `task_struct` via shared memory: ! `task_struct` changes over the time, tightly coupled
> * `/proc/pid/...`: inefficient, cannot provide low latency
>
> Messages: thread created/blocked/preempted/yield/dead/wakeup/affinity or a timer tick with a **timestamp**
>
> Message Queue: every agent listens on a message queue, a native thread sends status updates to only one message queue(how to assign?), implementation: **custom** queue in shared memory(BPF ring buffer and `io_uring` are great but they only support high kernel version)
>
> thread-queue association: initially there is a default queue after an enclave is created, agent can create/destroy queue, a new thread is assigned to the default queue by default, but this can be changed via a system call named `ASSOCIATE_QUEUE`
>
> queue-agent association: can be configured, but it is trivial at most of the time
>
> move threads across queues/CPUs for flexibility via `ASSOCIATE_QUEUE`
>
> $A_{seq},T_{seq}$ is incremented when an agent receives a message or a thread sends a message, they are memory-mapped, we call this **status words**

agent-to-kernel: decision, via transactions or system calls

enclaves are separated depending on the **topology** of the system. This design also provides good fault isolation.