[link](https://developer.arm.com/documentation/102412/latest)

## Different privilege levels

privilege only changes when PE takes or returns from an exception(does this mean that we cannot use something like `sret` in RISC-V to downgrade the privilege level?)

EL0 for application, EL1 for OS, EL2 for hypervisor, EL3 for firmware

memory privilege, privileged(EL1-3) and unprivileged(EL0) memory accesses are checked separately, translation tables are stored in memory, also MMU registers

register access, combination of **system registers** defines current context of PE, `<reg-name>_<lowest-privileged-level>`, for example, `TTBR0_EL1` cannot be accessed from EL0, otherwise an exception will be generated

system registers with different exception levels are independent and encoded differently,

hint: EL0 and EL1 share the same MMU configuration

## Execution states and security states

current state is determined by current Exception Level and **Execution State**, which defines the width of general-purpose registers and which instruction set to use, execution state also affects the memory model and how exceptions are managed, we only focus on `aarch64`, where GP registers are 64-bit and instruction set `A64` is used(for execution state `aarch32` there are multiple available instruction sets such as `T32` and `A32`)

**Security State**, briefly speaking, it is about *trusted* or not; there are 2 security states:

* secure: can access secure/non-secure physical address spaces and system registers, can only ack secure interrupts
* non-secure: can only access non-secure physical address spaces and system registers, can only ack non-secure interrupts

RME(Realm Management Extension) of armv9-a introduces 2 extra security states:

* realm state
* root state

currently, we do not need to change execution states

change security states: can only be configured in EL3, EL3 is always secure in armv8-a

EL0/EL1 is required whereas EL2/EL3 is optional

## Exception types

Exceptions: the event that PE has to suspend the current execution and change its state to handle it

sync exceptions: caused by, or related to recently executed instructions, *sync to the execution stream*, for example, invalid instruction/misaligned memory access/system call instructions: `SVC`, `HVC` and `SMC`/debug exceptions

asynchronous exceptions: generated externally, can be temporarily masked, which means that "it can be left in a pending state before the exception is taken", including:

* physical interrupts: SError(System Error)/IRQ/FIQ
* virtual interrupts: vSError/vIRQ/vFIQ

IRQ and FIQ have the same priority since armv8, they are independent and are used to implement secure and non-secure interrupts(see GIC guide)

In 2021, armv8.8-a and armv9.3-a adds support for NMI(non-maskable interrupts), which means that some interrupts have superiority so that it can be taken although `PSTATE` are configured to masks it, not delving it too much

SError: aysnc error after passing all the checks of MMU, maybe from cache or the memory bus

## Exception handling

from exception table-> save/restore current context -> specific handler

exception: taken from->taken to=return from->return to

each exception should be handled at a specific exception level, however, interrupts can be routed to different exception levels

taking an exception: hardware save `ra` and current `PSTATE`(stored in `SPSR_ELx`, Saved Program Status Registers, and `ELR_ELx` respectively, where `x` is the exception level the exception is taken to), update `PSTATE` according to which exception is being taken, branch to the exception handler in the vector table

IRQ/FIQ/SError can be independently routed to EL1/EL2/EL3, see `SCR_EL3`(Secure Configuration Register) and `HCR_EL2`(Hypervisor Configuration Register)

Control Execution State after taking an exception: see `SCR_EL3/HCR_EL2.RW`, not useful

return from an exception: SW uses `ERET` instruction, then HW restore `PSTATE` from `SPSR_ELx` and branch to `ELR_ELx` atomically

exception stacks: `SP_EL0` and `SP_ELx` are used where `x` is the current exception level, normally all code runs on `SP_EL0`, after taking an exception `SP_ELx` is initially selected, which makes it easy to handle exceptions from stack overflows

vector table: `VBAR_ELx`(Vector Base Address Register) where `x` is 1/2/3 should be configured by SW before interrupts are enabled, vector table can be divided into 4 parts(from a lower EL, from the same EL while using `SP_EL0 `, from the same EL while using `SP_ELx`)

 



