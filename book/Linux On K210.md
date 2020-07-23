# Linux On K210

## [k210-linux-nommu](https://github.com/vowstar/k210-linux-nommu)

:cry: Kernel panicked on MaixDock...

```
[    0.273196] Run /sbin/init as init process
[    0.277380] Run /etc/init as init process
[    0.281367] Run /bin/init as init process
[    0.287698] init[1]: unhandled signal 4 code 0x1 at 0x0000000080591790
[    0.293472] CPU: 1 PID: 1 Comm: init Not tainted 5.6.0-rc1vowstar #3
[    0.299802] epc: 0000000080591790 ra : 000000008059178a sp : 00000000805cbe50
[    0.306920]  gp : 00000000805bca80 tp : 0000000000000000 t0 : 0000000000000000
[    0.314127]  t1 : 00000000805cbe11 t2 : 0000000000000000 s0 : 00000000805cbf88
[    0.321333]  s1 : 00000000805cbfb8 a0 : 0000000000000001 a1 : 0000000000000000
[    0.328540]  a2 : 00000000805cbe11 a3 : 00000000805cbe08 a4 : 0000000000000000
[    0.335746]  a5 : 00000000805cbfc6 a6 : 00000000805cbe10 a7 : 00000000805cbe10
[    0.342952]  s2 : 00000000805c70d0 s3 : 0000000000000002 s4 : 000000008059a050
[    0.350158]  s5 : 00000000805cbe50 s6 : 000000000000000e s7 : 0000000000000000
[    0.357365]  s8 : 0000000000000000 s9 : 0000000000000000 s10: 0000000000000000
[    0.364571]  s11: 0000000000000000 t3 : 00000000805cbe00 t4 : 0000000000000000
[    0.371774]  t5 : 0000000000000000 t6 : 0000000000000000
[    0.377075] status: 8000000000006000 badaddr: 0000000008000008 cause: 0000000000000002
[    0.385245] Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000004
[    0.392622] CPU: 1 PID: 1 Comm: init Not tainted 5.6.0-rc1vowstar #3
[    0.398947] Call Trace:
[    0.401384] [<00000000801ae2f2>] 0x00000000801ae2f2
[    0.406244] [<00000000801ae436>] 0x00000000801ae436
[    0.411106] [<000000008027f86e>] 0x000000008027f86e
[    0.415968] [<00000000801b14d8>] 0x00000000801b14d8
[    0.420830] [<00000000801b34aa>] 0x00000000801b34aa
[    0.425693] [<00000000801b396e>] 0x00000000801b396e
[    0.430554] [<00000000801ba258>] 0x00000000801ba258
[    0.435416] [<00000000801adcae>] 0x00000000801adcae
[    0.440279] [<00000000801ad304>] 0x00000000801ad304
[    0.445141] SMP: stopping secondary CPUs
[    0.449064] ---[ end Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000004 ]---
```

## [K210-Linux0.11](https://github.com/lizhirui/K210-Linux0.11)

Port Linux 0.11 on K210, and run on M mode.

We have to build it on Visual Studio 2019, however, we can find a built image [here](https://en.bbs.sipeed.com/uploads/short-url/iLY5gAU1WaY7kurWenQIPBRzR8w.zip).

Luckily it worked, though the only command supported it 'ls' :smile:

It is based on Kendryte K210 standalone SDK, so maybe it's relatively easy for me to read the code.