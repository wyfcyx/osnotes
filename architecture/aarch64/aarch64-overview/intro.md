[link](https://developer.arm.com/documentation/102404/latest)

processor/core is also called a PE(Processing Element) in Arm's context

A(Applications, for desktop)->R(Real-time, for ...)->M(Microcontroller, for IoT)

A/R/M-profile processors can be mixed in a real system such as a smart phone

**architecture** is a function specification of hardware which involves:

* instruction set
* register set
* exception model
* memory model
* debug, trace and profiling

Arm architecture provides ISA compatibility for applications, on top of that, BSA(Base System Architecture) describes interrupt controllers or timers for OS, and BBR(Base Boot Requirements) specifies BIOS/ACPI for firmware

other important specifications in a SoC:

* GIC(Generic Interrupt Controller)
* System Memory Management Unit(SMMU or IOMMU)
* Generic Timer
* Server/Trusted Base System Architecture
* AMBA, Advanced Microcontroller Bus Architecture

