## OpenSBI 启动 K210 流程分析

* `sbi_init.c/sbi_init` 函数。

  从陷入死循环的情况来看，应该后续是进入了 `init_coldboot` 函数。