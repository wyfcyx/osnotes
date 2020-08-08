# RVM 与 zCore Hypervisor

* Hypervisor = VMMonitor，虚拟机管理器，单机运行多个 OS
* RVM = rCore Virtual Machine, written in Rust, can be used in rCore/zCore
* now we can run $\mu$core on rCore

## basic concept

* guest has the same Arch as host, hardware virt

* CPU host/guest mode

* VM entry -> VM exit, such as interrupt

* x86 virtualization support: Intel/AMD

* Hypervisor type 1/2

  1: guest OS -> Hypervisor -> Hardware

  2: guest OS -> Hypervisor(process of host OS) -> host OS -> Hardward, KVM/RVM, include Kernel Mode/User Mode

## overall architecture

* type2 like KVM+QEMU

* component

  1. Host OS: rCore/zCore or Linux
  2. RVM: a component of Host OS
  3. Hypervisor: a user mode application, comm with RVM by syscall
  4. Guest OS: run under the help of Hypervisor

* between RVM and Hypervisor, rCore and zCore have different APIs

  zCore: syscall `sys_guest_*, sys_vcpu_*`

  rCore: virtual devices, ioctl

## CPU Virtualization

* x86 only: Intel VMX instruction extension
* VMCS
  * control section
  * readonly section
  * Guest status(load when VM entry, save when VM exit)
  * Host status(opposite from up)
* VMX Instructions

## Memory Virtualization

* Extended Page Table

## I/O Virtualization

## Interrupt Virtualization

* Guest interrupt handled by Guest IDT