# 2.内存管理

## 2.1 物理内存初始化

 ### 2.1.1 内存管理概述

内核内存管理的相关模块：VMA管理、缺页管理、匿名页面、page cache、页面回收、反向映射、slab分配器、页表管理

### 2.1.2 内存大小

描述方式：设备树device tree，内核初始化的时候解析bootloader传进来的fdt获取可用的RAM区域

### 2.1.3 物理内存映射

### 2.1.4 Zone初始化

一种小技巧：通过在数据结构布局中插入padding，让一个数据结构的不同锁分布在不同的cache line中，以避免false sharing。比如这一节介绍到的`struct zone`就有`zone->lock`和`zone->lru_lock`两把锁。

我理解应该是通过`struct zone`把可用的物理页帧分组，当分配物理页帧用作某个用途的时候优先从一个固定的组中分配。

zone初始化的时候需要确定每个zone的范围。

有一个`zonelist`，是一个zone的链表，伙伴分配器会按照`zonelist`从头到尾的顺序尝试分配内存。

重要全局变量：`mem_map`，是一个`struct page`的数组。

### 2.1.5 空间划分

`PAGE_OFFSET`似乎指的是内核虚拟地址区间的起始地址

如何计算内核空间的线性映射？

### 2.1.6 物理内存初始化

在经过上面提到的初始化过程中，如何将物理页帧添加到buddy system中？

首先在Linux中有一个`MAX_ORDER`参数，Linux会将所有的物理页帧分成编号为0到`MAX_ORDER-1`这`MAX_ORDER`组，比如`MAX_ORDER`为11的时候，就有11个链表（这个多链表其实就是buddy system的实现），链表的单位分别是1,2,4,8,...,1024个连续物理页帧。这样就可以应对连续物理内存分配的需求。

buddy system空闲页帧的管理层级结构如下：首先是按照zone（比如可以有`ZONE_NORMAL`和`ZONE_HIGHMEM`这两类），每个zone有一个`free_area[MAX_ORDER]`数组，每个`free_area`又分成`MIGRATE_TYPES`个链表，链表中的每个元素是对应order的一个页块。

迁移类型`MIGRATE_TYPES`包括unmovable, reclaimable, movable, reserve等。

观察可以发现，大多数物理页帧存放在movable链表中；初始化之后大部分物理页帧存放在order=10的链表中。

内存管理中有一个page block的概念，大小为order=`MAX_ORDER-1`的一个连续页块。每个page block都需要4字节存储空间`pageblock_flags`指出该page block的迁移类型`MIGRATE_TYPE`。zone里面所有page block的`pageblock_flags`是以zone为单位统一分配的。这些page block的迁移类型可以被修改。

在初始化的时候，对于每个可用的物理内存区间，均从头到尾，每次按照最大可能（考虑当前起始地址的对齐）的order加入到对应的链表中，并将迁移类型设置为movable。

## 2.2 页表的映射过程

感觉有点体系结构相关，先不看了。

### 2.2.1 ARM32页表映射

## 2.3 内核内存布局

仅考虑64位的就好，跟想象中没有很大区别。

### 2.3.1 ARM32内核内存布局

## 2.4 分配物理页面

### 2.4.1 伙伴内存分配系统

内核中分配物理页面的接口`alloc_pages(gfp_mask, order)`，前者表示分配掩码，后者支持需要分配连续$2^{\text{order}}$个物理页面。分配掩码分为两类：zone modifiers和action modifiers，前者表示从哪个zone中分配，后者会改变分配行为。
