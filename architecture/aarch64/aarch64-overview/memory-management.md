## Different address spaces

### Virtual address spaces

NS.EL0/NS.EL1(Non-secure, OS/Application)->`TTBRn_EL1`->physical memory map seen by guest OS->`VTTBR0_EL2`(Virtualization tables)->physical memory(virtual address->intermediate physical address,IPA->physical address)

NS.EL2(Non-secure Hypervisor virtual memory map)->`TTBR0_EL2`->physical memory

EL3(Secure Monitor virtual memory map)->`TTBR0_EL3`->physical memory

There are also secure EL0/1/2 address spaces. They are "translation regimes".

`NS.EL2:0x8000` means virtual address `0x8000` in non-secure EL2 virtual address space

### Physical address spaces(PAS)

Non-secure PAS0/Secure PAS/Realm PAS/Root PAS

The current security state(Non-secure/secure/realm/root state) of the processor controls which PAS a virtual address can map to.

can map to multiple PAS->translation table entry controls which specific PAS to map to

### Size of virtual spaces

for EL0/EL1, user space: `0x0-0xF_FFFF_FFFF_FFFF`, kernel space: `0xF000_0000_0000_0000-0xFFFF_FFFF_FFFF_FFFF`, they have separate translation tables

> if HCR_EL2.E2H is 1, then OS runs in EL2 and the kernel space is for EL2

for EL3/EL2(HCR_EL2.E2H is 0), there is only a single space: `0x0-0xF_FFFF_FFFF_FFFF`

Here virtual address has 52 bits, but they can be independently shrunk to a smaller size: `TCR_EL1.T0SZ` and `TCR_EL1.T1SZ` control size of EL0/EL1's address space($2^{64-\text{TnSZ}}$) respectively.

all armv8-A implementations support 48-bit address spaces, support for 52-bit address spaces depends on `ID_AA64MMFR2_EL1`.

### Size of physical spaces

armv8.0-A, a maximum of 48 bits; armv8.2-A, a maximum of 52 bits, see `ID_AA64MMFR0_EL1`

configure intermediate physical address space: for example, `VTCR_EL2.T0SZ`($\leq$physical address space size)

### ASID

use ASIDs to decrease the number of TLB invalidation during a context switch

for EL0/EL1 translations can be marked as G(Global) or nG using the `nG` bit of the translation table entry, global apply whichever application is running, non-global only apply with a specific application and are tagged with an ASID in the TLB

current ASID is stored in `TTBR0_EL1`(EL0, application) and `TTBR1_EL1`(EL1, kernel)

### VMID(Virtual Machine Identifier)

it is used with ASID, so do not forget to set up it even if you do not use a hypervisor

### Common not Private

VMID and ASID across multiple cores,

armv8.0-A, different cores use VMID and ASID differently,

armv8.2-A, after `TTBR.CnP` bit is set, SW guarantees that VMID and ASID are used in the same way across all the cores, which means that **TLB entries can be shared**

## Translation Table Entries

each is of 8 bytes, ignore attribute details now...

* Table Descriptor, can occur in level 0/1/2, bottom 2 bits: 11, contains next-level table address
* Block(Huge Page) Descriptor, can occur in level 1/2, bottom 2 bits: 01, contains output block address
* Page Descriptor, can occur in level 3, bottom 2 bits: 11, contains output page address

## Translation granule

smallest block of memory: 4KiB/16KiB/64KiB(12/14/16 bits) are supported by aarch64, reported by `ID_AA64MMFR0_EL1`

4KiB, 48-bit VA only, 9-9-9-9(-12), size per entry: 512GiB-1GiB-2MiB-4KiB, output 48-bit PA

16KiB, 48-bit VA only, 1-11-11-11(-14), size per entry: 128TiB-64GiB-32MiB-16KiB, output 48-bit PA

64KiB, 52-bit VA, 10-13-13(-16), size per entry: X-4TiB-512MiB-64KiB, output 52-bit PA

`TCR_EL1.TG0` and `TCR_EL1.TG1` can control translation granule of the user space and the kernel space respectively

depend on `TGn` and `TnSZ`, page translation starts from different level of translation table

system registers related to address translation:

* `SCTLR_ELx`: M(enable MMU)/C(data and unified cache)/EE(endianness of page walking)
* `TTBR0_ELx` and `TTBR1_ELx`: BADDR(translation table base address)/ASID(only for non-global translations)
* `TCR_ELx`: PS or IPS(size of physical space size)/`TnSZ` and `TG`/etc.
* `MAIR_ELx`: `Attr`(type and cacheability in state 1 tables)

## TLB maintenance

invalidate TLB entries after modifying a translation entry or changing how translation entries are interpreted, for example:

* unmap an address
* change the mapping of an address
* change the way the tables are interpreted

TLB invalidation instruction: `TLBI <type> <level>{IS|OS} {,<xt>}`

* type: ALL/VA(match VA and ASID)/VAA(match VA, any ASID)/ASID(match ASID)
* level: E1(for EL0/1)/E2/E3
* `<IS|OS>`: operation is inner shareable or outer shareable, broadcast to inner/outer shareable domain(added in armv8.4-A)
* `<xt>`: address of ASID

## Address translation instruction

instruction `AT`(Address translation) writes to `PAR_EL1`(Physical Address Register)

