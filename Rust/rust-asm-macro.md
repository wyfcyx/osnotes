类似于`println!`宏，`asm!`宏的前面为若干条指令字面量，中间可以出现`{0}`或`{1}`之类对于后面给出的参数的指代（如果没有数字的话就是完全按照顺序来）。`in(reg) <variable name>`指的是将上下文中的某变量绑定到一个寄存器上作为输入，同理有`out(reg)`和`inout(reg)`。如果是`inout`且输入/输出为不同变量，那么`<variable name>`部分可以通过`<invar> => <outvar>`来同时指定输入和输出变量。当需要常数的时候，字面量中可以用`{number}`，参数列表中可以给出`number = const 5`。

出于性能考虑，我们总是希望使用更少的寄存器，如果单纯使用`in/out/inout`的话这些寄存器*应该都是*不同的。在某些情况下我们可以使用`lateout`或`inlateout`，它可以用于当所有输入均被消耗掉之后才最终被修改的一个输出（一般来说应该位于最后一条指令？），这时它即可复用那些用于保存输入的寄存器而不必担心冲突。

`reg`可以显式替换为一个具体的寄存器，如x86中的`"eax"`。但是这种参数不能在字面量中通过`{}`来指代，且必须出现在参数列表的结尾（即任何其他类型参数都必须出现在它之前）。下面是一个手动通过汇编实现乘法的例子：

```rust
fn mul(a: u64, b: u64) -> u128 {
    let lo: u64;
    let hi: u64;

    unsafe {
        asm!(
            // The x86 mul instruction takes rax as an implicit input and writes
            // the 128-bit result of the multiplication to rax:rdx.
            "mul {}",
            in(reg) a,
            inlateout("rax") b => lo,
            lateout("rdx") hi,
        );
    }

    ((hi as u128) << 64) + lo as u128
}
```

某些指令可能会修改多个寄存器，其中某些结果并一定是我们想要的，但是我们也必须将它们在参数列表中声明出来，因此它们实际上会被覆盖，我们需要通知编译器做好保存和恢复工作。例如下面是一段在x86平台上获取L1缓存容量的代码：

```rust
let ebx: u32;
let ecx: u32;

unsafe {
    asm!(
        "cpuid",
        // EAX 4 selects the "Deterministic Cache Parameters" CPUID leaf
        inout("eax") 4 => _,
        // ECX 0 selects the L0 cache information.
        inout("ecx") 0 => ecx,
        lateout("ebx") ebx,
        lateout("edx") _,
    );
}

println!(
    "L1 Cache: {}",
    ((ebx >> 22) + 1) * (((ebx >> 12) & 0x3ff) + 1) * ((ebx & 0xfff) + 1) * (ecx + 1)
);
```

`cpuid`指令需要输入参数为`eax/ecx`两个寄存器，会修改`eax/ebx/ecx/edx`全部四个寄存器，但是这里我们只需要`ebx/ecx`两个结果。于是不用的寄存器我们可以将输出变量绑定为`_`代表这个值可以直接丢掉。注意到所有相关的寄存器（可以称为一个完整的clobbered list）我们都列举出来了，这样就不会有寄存器内容丢失的隐患了。

同样还有下面这种请求编译器分配一个临时寄存器的情况：

```rust
// Multiply x by 6 using shifts and adds
let mut x: u64 = 4;
unsafe {
    asm!(
        "mov {tmp}, {x}",
        "shl {tmp}, 1",
        "shl {x}, 2",
        "add {x}, {tmp}",
        x = inout(reg) x,
        tmp = out(reg) _,
    );
}
assert_eq!(x, 4 * 6);
```

另外一种特殊的参数类型为`sym <symbol-name>`，这里的`<symbol-name>`可以是函数名或者全局变量名，编译器会直接将它的地址传进去而无需我们做手动的转换操作。值得一提的是即使函数或变量名没有设置为`#[no_mangle]`我们也可以直接填入`<symbol-name>`，编译器会帮助我们转换为混淆后的名字。下面是一段手动进行函数调用的代码：

```rust
extern "C" fn foo(arg: i32) {
    println!("arg = {}", arg);
}

fn call_foo(arg: i32) {
    unsafe {
        asm!(
            "call {}",
            sym foo,
            // 1st argument in rdi, which is caller-saved
            inout("rdi") arg => _,
            // All caller-saved registers must be marked as clobberred
            out("rax") _, out("rcx") _, out("rdx") _, out("rsi") _,
            out("r8") _, out("r9") _, out("r10") _, out("r11") _,
            out("xmm0") _, out("xmm1") _, out("xmm2") _, out("xmm3") _,
            out("xmm4") _, out("xmm5") _, out("xmm6") _, out("xmm7") _,
            out("xmm8") _, out("xmm9") _, out("xmm10") _, out("xmm11") _,
            out("xmm12") _, out("xmm13") _, out("xmm14") _, out("xmm15") _,
        )
    }
}
```

从中可以看出，我们可以通过将`out(<specific register>) _`加入参数列表的方式来要求编译器在执行汇编指令前后保存和恢复该寄存器。在这里我们用这种方式来保存和恢复所有的调用者保存寄存器。

最后一个参数可以为`options`来让编译器更加了解该段汇编代码的行为从而能够更容易做出针对性优化。比如下面的一段汇编代码：

```rust
let mut a: u64 = 4;
let b: u64 = 4;
unsafe {
    asm!(
        "add {0}, {1}",
        inlateout(reg) a, in(reg) b,
        options(pure, nomem, nostack)
    );
}
assert_eq!(a, 8);
```

三个options分别表示汇编代码没有可以观察到的副作用（因此可能会被编译器直接消除）；不会访存；也不会向栈上push数据。目前一共有下面这些options:

* pure:汇编块没有副作用，且输出仅取决于直接输入或从内存中读到的值（编译器会减少调用它的次数）
* nomem:汇编块中不涉及内存读写（编译器会跨汇编块将已修改的全局变量保存在寄存器中因为它们在此期间不会被读写）
* readonly:汇编块中不涉及内存写入（编译器会跨汇编块将未修改的全局变量保存在寄存器中因为它们在此期间不会被修改）
* perserves_flags:汇编块不会修改标志位寄存器，这样编译器在汇编块结束后不必重新计算标志位
* noreturn:汇编块永远不会返回，或返回值类型为`!`，表现像是一个不会返回的函数。注意在它被调用之前，作用域内的局部变量不会被释放。
* nostack:汇编块不会向栈上压数据。如果未设置此选项，栈指针一定会被对齐。
* att_syntax:仅用于x86架构。