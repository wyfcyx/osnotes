## 1 intro

> **state spill**
>
> modularization is critical to achieve many design goal of operating systems
>
> however, modularization itself it not enough, we should also consider the interactions between modules
>
> challenge: how states change and propagate throughout the system
>
> main reason->state spilling: for an entity, its interaction with another entity has a **long-term** effect on itself
>
> transactions: synchronous communication(involves transfer of control) between entities, for example, function/system calls, interrupts, signals, ...

state spill poses a threat to some computational goals in the OS(for example, evolvability or availability)

reliability is important in system software since there is no hardware redundancy

realization of the Rust prototype: mitigating state spill, statically ensuring some correctness invariants

contributions: module separation with clear boundaries; intralingual design(rely on the compiler to find errors or ensure invariants at compile time)

the great potential of Theseus's design: live evolution(more flexible than prior systems; ) & fault recovery(graceful exception handling)

do not have a huge performance penalty, but it is complicated to analysis?

**only 72 unsafe code blocks among the 38KLoC codebase???**

## 2 Rust

## 3 Overview and Design Principles

cell(in biology): unit of modularity, core building block of the OS

all software written in safe Rust run in a single address space(SAS) and a single privilege level(SPL, for sure?)

> Why are OS components and application run in the same privilege level?

### 3.1 runtime-persistent cells

cell: clear bound, **a Rust crate in fact** or an object file(this applies to **all** cells)

cells are loaded and linked into the system at runtime **on demand**, Theseus **manually** implements a linker which finds object files in the disk, loads them into memory and relocates symbols **recursively**. In this way, **cell metadata** is constructed, which is essential for *live evolution and fault recovery*

each loaded cell: mapped pages & sections with symbols and dependencies(both incoming and outgoing)

cell-oriented management(everything throughout the system is a cell!): allow **cell swapping** in general; joint cell evolution across multiple system layers

tiny crates without submodules(mod xxx in a rust crate) since these information is lost: flatten organization; more programmer-friendly; easier cell swapping

### 3.2 bootstrapping Theseus

nano-core: basic cells statically linked, a base kernel executable, load other cells at runtime, unload itself at the final stage

## 4 Power to the language

intralingual: match Theseus's execution environment to Rust's runtime model 

benefits: automatic resource management relying on Rust, mitigating the burden of OS; end-to-end safety checks, runtime->compile time errors

By contrast, existing extralingual design relies on hardware safety guarantees and runtime checks

### 4.1 matching the language's RT model

language's RT model(including Rust): run in single address space & privilege level, for example, a single process

thus, in Theseus, SAS & SPL & only one global dynamic memory allocator

### 4.2 intralingual OS design

how the compiler *understand* the OS semantics: "exposing safety requirements, invariants and semantics to the compiler"

almost in safe Rust

ensuring invariants: for example, using `&T/Arc<T>` to share resources instead of raw pointers

using lossless interfaces which keep the language contexts intact for both external/internal functions; opposite: binary interfaces where the type and lifetime are lost

how to avoid resource leakage: `Drop` trait + **stack unwinding**, unwinder in Rust: invoked on an exception or a task is requested to be killed, based on compiler-emitted information and cell metadata

2 ways of resource revocation: killing and unwinding an uncooperative task; cooperative

### 4.3 examples of intralingual systems

#### 4.3.1 memory management

a contagious virtual memory region: `MappedPages` with mapped physical pages `AllocatedFrames` and virtual pages `AllocatedPages`

compulsory one-one VA->PA mapping; boundary check; **invalidating TLB & clear PTE** on a drop;

#### 4.3.2 task management

minimized; `spawn_task` instead of `fork` since `fork` cannot guarantee memory safety; multiple release paths(not only dropping the `Task` object, an exceptional one: into the wrapper->crash->unwind the stack->mark the task as crashed->cleanup the task); **each task owns the cell(including all mapped sections) which contains the task's entry function**, and each cell owns the cells it depends on





