被PMP折磨过很多次，这次直接写一点笔记。

PMP项每个位宽为8，对于RV64来说，each `pmpcfg` register contains 8 PMP entries, only even `pmpcfg` registers are available on RV64,

`pmpaddr`: [55:2] of 56-bit physical address

PMP entry: 0R,1W,2X,[3:4]A,7L

A: OFF=0, disabled; TOR=1; NA4=2; NAPOT=3;

NAPOT(naturally aligned power-of-two region, $\geq$8bytes)

`pmpaddr` ends with 0=>8B, 01=>16B, 011=>32B, which means that 01...x...1=>$2^{x+3}$B

> 1000 ends with 0, 1-1, (1000>>3)-1
>
> 10000 ends with 01, 10-1, (10000>>3)-1
>
> 100000 ends with 011, 100-1,(100000>>3)-1
>
> ...
>
> btw, (100>>3)-1 is undefined?

TOR(top of range), match address $y$ satisfies $pmpaddr_{i-1}\leq y<pmpaddr_i$ if $entry_i.A=TOR$ irrespective of $entry_{i-1}$

NA4(naturally aligned 4-byte region)

`pmpcfg0(0x3A0)~pmpcfg15(0x3AF)`, `pmpaddr0(0x3B0)~pmpaddr63(0x3EF)`

