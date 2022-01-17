[link](https://developer.arm.com/documentation/102374/latest/)

## Registers

GP registers, `X0-X30` and `W0-W30`, where `W0` is the bottom 32 bits of `X0`

when `W0` is written, top 32 bits of `X0` are also set to zero

other registers: `WZR/XZR` are read-only zero registers, `SP`(current stack pointer, that is `SP_ELx`) is **not a GP register** and only some of the data processing instructions can operate it,  `X30` is `LR`(Link register),  `PC` is not a GP register and we can use `ADR Xd, .` to read it where `ADR` returns the address of a label and `.` indicates the current position

> In A32 and T32 instruction sets `PC` and `SP` are GP registers.

system registers: load system registers `MRS Xd, <system reg>`; store system registers `MSR <system reg>, Xd`;

## Instructions

### Data processing

* Arithmetic/logic operations: `ADD W0, W1, W0`(first destination then inputs), `ADD W0, W1, #1`(constant as the second input), `ADDS W0, W1, W0`(update ALU flags according to the result), `MOV` and `MVN`(Move and Move negative) only receive 1 input
* [Bit manipulation](https://developer.arm.com/documentation/102374/0101/Data-processing---bit-manipulation)
* Extension and Saturation: `SXTx/UXTx` where `x` can be `B/H/W` extends a part of the input and save the result to the output; not interested in saturation
* [Format conversion](https://developer.arm.com/documentation/102374/0101/Data-processing---format-conversion): from float to integer register or the other direction
* not interested in SIMD

### Load and stores

* Basic: `LDR<sign><size> <Dest>, [<Addr>]` and `STR<size> <Dest>, [<Addr>]`
* Size control: `STRB/STRH/STRW`
* zero and sign extension: `LDRB W4, <addr>` zero extends a byte to a word, `LDRSB W4, <Addr>` sign extends a byte to a word
* addressing
  1. base only, `LDR W0, [X1]`
  2. base+offset, `LDR W0, [X1, #12]`
  3. pre-index, `LRD W0, [X1, #12]!`, load from address `X1+12`, and `X1` is updated to this address
  4. post-index, `LRD W0, [X1], #12`, load from address `X1`, and then `X1` is updates to `X1+12`
* load/store pairs: `LDP/STP` can load/store 2 registers at a time
* skip SIMD registers

### Program flows

* unconditional branch: `B <label>`, direct(or PC-relative), encoded with the offset(+-128MiB) from the current PC; `BR <Xn>`, branch with register, indirect(or absolute)

* conditional branch: `B.<cond> <label>`, PC-relative, offset(+-1MiB, smaller range since some bits are used to store conditions), according to ALU flags in `PSTATE`(NCVZ, Negative, Carry, Overflow, Zero); `CBZ <Xn> <label>` and `CBNZ <Xn> <label>`; `TBZ <Xn>, #<imm>, <label>` and `TBNZ <Xn>, #<imm>, <label>`, like `CBZ` and `CBNZ` but only test a single bit; **no conditional indirect branch in A64**

* instructions that can update ALU flags except for data processing instructions

  1. `CMP X0, X7` is an alias of `SUBS XZR, X0, X7`
  2. `TST W5, #1` is an alias of `ANDS WZR, W5, #1`

* conditional selects: substitute branches in some simple cases and improve performance

  for example, `CSEL Xd, Xn, Xm, cond` means that: if `cond` then `Xd:=Xn` else `Xd:=Xm`

* function call: `X30(LR)`, `B->BL` or `BR->BRL` will write the return address to `LR`, then `RET` can branch indirectly to `LR`; use `RET` instead of `BR LR` can help branch prediction

## Calling convention

`X0-X7`: parameters and results

`X0-X15` can be corrupted by callee, whereas `X19-X28` are callee-saved

`XR(X8)` is an indirect result register which points to an resulting struct

`IP0(X16)` and `IP1(X17)` are intra-procedure-call(between the function is called to its first instruction is executed) corruptible registers, linkers can use them to insert small pieces of code between caller and callee

`FP(X29)` frame pointer

`LR(X30)` link register

## System calls

`SVC`, Supervisor Call, from EL0 to EL1

`HVC`, Hypervisor Call, from EL1 to EL2

`SMC`, Secure Monitor Call, from EL1/2 to EL3

if `SVC` on EL2: handle it in EL2 instead of EL1, the reason for that is EL should not drop after taking an exception