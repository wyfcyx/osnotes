# x86虚拟化简介

## 虚拟机架构

支持两类软件：

* VMM：作为主机，提供给guest软件虚拟CPU的抽象并允许guest软件直接在逻辑CPU上执行。VMM可以选择性的保持对CPU资源、物理内存、中断管理和I/O的控制。
* Guest软件：每个虚拟机VM都是一个guest软件，支持一套OS+应用程序的软件栈。它们两两独立运行，调用由物理平台提供的访问各种资源的接口。软件栈表现的像是它们运行在裸机平台上一样。VM需要运行在较低特权级上，这样VMM才能控制它们。

## VMX操作简介

有两种VMX操作：VMX root和VMX non-root操作。一般情况下，VMM运行在root模式而VM运行在non-root模式。二者之间的转换称为VMX transitions。root进入non-root模式的转换被称为vm entries，反之则被称为vm exits。

root模式下的CPU行为与普通模式下较为接近，显著的区别在于：一组新的VMX指令变为可用等。non-root模式下的行为被限制并被修改以适用虚拟化。包括VMCALL在内的一些指令和事件会导致vm exit到VMM。因为这些vm exits替换了原本的行为，non-root模式下的软件功能是受限的。正是如此，VMM才能控制VM保持各种资源的控制。

并不存在软件可见的标志位指出一个逻辑CPU是否在non-root模式下运行。这样VMM可以阻止VM确定它是否是一个虚拟机。

## VMM软件生命周期

* 软件通过执行VMXON指令进入VMX模式；
* VMM可以通过VM entries进入VM，同一时间只能进入一个VM。VMM可以使用VMLAUNCH和VMRESUME等指令影响VM entry。VM exit之后控制权回到VMM。
* VM exit将控制权交给VMM设定的入口点。VMM可以根据VM exit的原因进行适当处理并通过VM entry回到虚拟机。
* 最终，VMM可以通过VMXOFF来销毁自己并退出VMX模式。

## 虚拟机控制结构

non-root模式和VMX转换被一个叫做VMCS的数据结构控制。

## 确认CPU是否支持VMX拓展

