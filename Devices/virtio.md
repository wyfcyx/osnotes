没有找到之前virtio的记录，那么在这里留一点。

## virtio设备组成部分

virtio设备有以下组成部分：设备状态、特性标志位、通知、设备配置空间和一个或多个virtqueue。

### 设备状态

通过驱动程序初始化设备遵循一个固定的流程，而设备状态指出流程进行到了哪一步。

驱动初始化设备的流程如下：

1. 重置设备
2. 设置ACK状态位，表明guest OS发现该设备；
3. 设置DRIVER状态位，表明guest OS知道如何驱动该设备；
4. 读取设备特征位，并写回一个guest OS和驱动程序支持的子集（在这个过程中驱动可以读取但不能写入设备的配置空间）；
5. 设置FEATURES_OK状态位，在此之后驱动就不能接受新的特征位；
6. 读取设备状态，确认FEATURES_OK仍然被置位（不然的话，说明设备不支持我们提交的特征子集或者设备不可用）；
7. 进行设备特定的配置；
8. 设置DRIVER_OK状态位。

### 特征位

兼容性：老驱动可以不接受新设备的新特性；新驱动可以知道老设备不支持某项新特性。

### 通知

有三种不同的通知：配置变更通知、available buffer通知和used buffer通知。

前两者由设备发送给驱动程序（请求完成，通过中断），后者由驱动程序发送给设备（提交请求，通过设备寄存器）。

### 设备配置空间

保存初始化后几乎不变的参数。

### 虚拟队列

只考虑向下兼容的Split Virtqueue。

每个队列有一个16位的queue size表示队列中最多同时有多少缓冲区。

每个virtqueue分为三个区域，每个区域在物理内存中连续存储并且有各自的对齐需求。

* 描述符表对齐到16字节，大小为16乘以queue size；
* 可用环对齐到2字节，大小为6+2乘以queue size（驱动写，设备读）；
* 已用环对齐到4字节，大小为6+8乘以queue size（设备写，驱动读）。

驱动提交请求（或者叫缓冲区，一个请求对应一个或多个缓冲区）：在描述符表中填充一个槽位（或者链接多个槽位），然后将描述符索引写入可用环（这里应该插入同步屏障），然后通知设备（即可用环通知）。

设备完成一个请求：将描述符索引写入已用环，并发送已用环通知。

如果使用legacy接口的话，对于三个区域的内存布局有额外的要求。

描述符布局：

```c
struct virtq_desc {
    /* Address (guest-physical). */
    le64 addr;
    /* Length. */
    le32 len;
    /* This marks a buffer as continuing via the next field. */
    #define VIRTQ_DESC_F_NEXT 1
    /* This marks a buffer as device write-only (otherwise device read-only). */
    #define VIRTQ_DESC_F_WRITE 2
    /* This means the buffer contains a list of buffer descriptors. */
    #define VIRTQ_DESC_F_INDIRECT 4
    /* The flags as indicated above. */
    le16 flags;
    /* Next field if flags & NEXT */
    le16 next;
};
```

每个描述对应一个缓冲区，只有设备和驱动中的其中一方能够写入（根据flags中的配置）。目前不考虑间接描述符。一串描述符中的每个缓冲区的写入者可以不同。

可用环布局（驱动写、设备读）：

```c
struct virtq_avail {
    #define VIRTQ_AVAIL_F_NO_INTERRUPT 1
    le16 flags;
    le16 idx;
    le16 ring[ /* Queue Size */ ];
    le16 used_event; /* Only if VIRTIO_F_EVENT_IDX */
};
```

ring中的每个元素表示一串缓冲区中最开头的缓冲区在描述符表中的位置。`idx`表示下一次驱动将写入ring数组的哪个位置。

已用环布局（设备写、驱动读）：

```c
struct virtq_used {
    #define VIRTQ_USED_F_NO_NOTIFY 1
    le16 flags;
    le16 idx;
    struct virtq_used_elem ring[ /* Queue Size */];
    le16 avail_event; /* Only if VIRTIO_F_EVENT_IDX */
};

/* le32 is used here for ids for padding reasons. */
struct virtq_used_elem {
    /* Index of start of used descriptor chain. */
    le32 id;
    /* Total length of the descriptor chain which was used (written to) */
    le32 len;
};
```

设备每次写入一个pair，`id`和之前可用环中写入的一样，`len`则表示设备一共向缓冲区中写入了多少字节。（如果驱动不知道设备会写入多少字节的话，为了避免信息泄露需要提前将整块缓冲区清零）。`idx`同样表示下一次设备会将pair写入到ring数组中的哪个位置。

驱动向设备提交缓冲区流程如下：

1. 在描述符表中放置缓冲区
2. 将描述符id插入到可用环的ring数组
3. 插入内存屏障，确保在下一步之前设备能够看到更新后的描述符表和可用环
4. 更新可用环的`idx`
5. 插入内存屏障，确保`idx`被更新
6. 向设备发送可用环通知

驱动读取已完成缓冲区流程如下：驱动需要自己保存一个`last_used_idx`...依此类推。

