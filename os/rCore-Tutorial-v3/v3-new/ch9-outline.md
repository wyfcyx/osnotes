## 9.1 同步互斥与内存顺序

多线程程序存在的必要性：性能！单核性能/频率遇到瓶颈

多线程程序的正确性：通过同步互斥来保护共享数据结构（临界区、...）

> 简单的多线程计数（基于pthread），多条指令间的interleaving导致错误，原子指令想必可解决该问题

软件同步方法解析（需要保证无论何种interleave的顺序均符合忙则等待/空闲则入的原则）

但是从现在的眼光看来

## 尚未

Rust的Send/Sync Trait分析；C/C++相比Rust可能出现的额外同步bug

