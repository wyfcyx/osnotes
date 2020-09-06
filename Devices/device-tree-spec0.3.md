## 术语解释
* AMP: 将 CPU 分成若干组，每一组上跑一个不同的 OS，这些 CPU 可能相同也可能不同
* cell：一个大小为 4 字节的信息单位
* interrupt specifier：描述一个中断的属性值，典型的内容包括中断号、中断优先级以及触发机制。
* unit address：节点名字的一部分，包含该节点在父节点地址空间中的地址

## Ch2. Device Tree

* boot program 将 device tree 加载到 client program 的内存，并将一个指向它的指针传给 client program

* dt 中每个节点都有若干个 property/value 对表示设备的属性，除了根节点之外每个节点有且仅有一个父亲

* 一颗 DTSpec-compliant 设备树描述系统中不必被 client program 动态探测的设备信息。

* 节点名：`node-name@unit-address`

  unit-address 的内容取决于节点所位于总线

  unit-address 必须与节点 reg property 的首个 value 相匹配；如果节点没有 reg property，则也不应该有 unit-address

  node-name 应尽可能通用，不局限于某个具体的编程模型

* 节点通过**绝对路径**唯一确定，如 /node-name-1/node-name-2/node-name-3

  若不引起歧义，`unit-address` 可以去掉

  若引起歧义，会发生未定义行为

* 节点的 property: (name, value)

* value 的类型有：

  empty: 也就是仅用该 property 是否存在来表达一个 true-false 信息；

  u32: 大端序；

  u64: 用两个大端序的 u32 表达；

  string: 沿地址递增，结尾为 `'\0'` 的若干个连续字节；

  prop-encoded-array: property 内部特定的格式；

  phandle: 一个 u32，用来引用设备树上的另一个节点。每个可引用的节点都需要定义一个 phandle 属性并赋予唯一的一个 u32 值。

  stringlist: 若干个 string 连接在一起，每个都用一个 `'\0'` 作为结尾。

* 接下来是一些标准属性，后面会提到，根据设备类型的不同，这些标准属性会有一些额外的限制。

* (compatible, stringlist)

  一个或多个字符串描述该设备的特定编程模型，用于 client program 从中选择合适的驱动程序，兼容性应按照从小到大的顺序排列。

  每个字符串推荐的格式为 `"manufacturer,model"`，分别代表生厂商和型号。

  例：```compatible = "fsl,mpc8641", "ns16550";```

* (model, string)

  描述该外设的生产商和型号，推荐格式为：`"manufacturer,model"`

* (phandle, u32)

  给每个可引用外设一个唯一的 u32 值，这样设备树中的其他外设就可以引用它。

  比如一个中断控制器定义如下：

  ```c
  pic@10000000 {
      phandle = <1>;
      interrupt-controller;
  }
  ```

  另一个外设可以挂在这个中断控制器下面：

  ```c
  another-device-node {
      interrupt-parent = <1>; // reference pic@10000000
  }
  ```

* (status, string)

  表示外设当前状态，可用的 value 包括：

  okay; disabled; reserved; fail; fail-sss

  （暂时不去关注它们各自代表什么语义）

* (#address-cells/#size-cells, u32)

  每一个有孩子的节点都需要提供这两个属性，它们不会从父节点继承，需要显式声明。分别表示每个孩子的 reg 属性的 address 域需要多少个 u32 来表示，以及每个孩子的 reg 属性的 size 域需要多少个 u32 来表示。

  若未提供的话，则 #address-cells=2, #size-cells=1

* (reg, prop-encoded-array)

  这里的 prop-encoded-array 是数目为人工确定的若干个 (address, length) pair

  用来表示设备资源在父亲总线地址空间中的位置，通常是指多个 MMIO 设备寄存器块的偏移量和长度，但视总线的类型不同也可能有不同的含义。若父节点是根节点，则地址被视为绝对地址。

  address, length 表达所需要的 u32 的个数分别由父节点的 #address-cells 和 #size-cells 定义。

* (virtual-reg, u32)

  与虚存有关，这里不纠结。

* (ranges, empty/prop-encoded-array)

  这里的 empty 或 prop-encoded-array 保存着若干个数目人工确定的 (child-bus-address, parent-bus-address, length) 三元组。

  提供一种定义总线地址空间（子地址空间）与总线节点父节点的地址空间（父地址空间）之间的转换的方法。应该是指当前的节点代表一个总线，其父亲代表其父总线，range 属性就定义在当前节点上。

  child-bus-address 是在（子，或称当前）总线地址空间中的一个物理地址，表达所需的 u32 的个数由当前节点的 #address-cells 属性确定；

  parent-bus-address 是父亲总线地址空间中的一个物理地址，所需的 u32 的个数由父节点的 #address-cells 属性确定；

  length 描述当前总线地址空间中 range 的大小，表达所需的 u32 的个数由当前节点的 #size-cells 属性确定。

  如果 ranges 是 empty，则表明父子地址空间是相同的，不必进行任何地址转换；如果一个总线节点上没有这个属性，我们假定该节点的孩子和该节点的父地址空间之间不存在任何映射关系。

  例子：

  ```c
  soc {
  	compatible = "simple-bus";
  	#address-cells = <1>;
  	#size-cells = <1>;
  	ranges = <0x0 0xe0000000 0x00100000>;
  	
      serial@4600 {
  		device_type = "serial";
  		compatible = "ns16550";
  		reg = <0x4600 0x100>;
  		clock-frequency = <0>;
  		interrupts = <0xA 0x8>;
  		interrupt-parent = <&ipic>;
  	};
  };
  ```

  在这个例子中，假设再上层就是根节点，则串口 MMIO 的实际物理地址区间是以 $\mathtt{0xE000\_4600}$ 开头的。

* (dma-ranges, empty/prop-encoded-array)

  应该跟 ranges 差不多，暂时跳过。

* 下面是一些和中断有关的内容。

* DTSpec 是对其他地方的中断树模型进行了改编，在设备树里面有一个逻辑中断树代表中断在硬件中的层级与路由。从技术上说，中断树一般被理解成一个有向无环图。

  中断源到中断控制器的物理连线在 DT 中用 interrupt-parent 属性来表示。那些能够产生中断的设备节点，一般都有一个 interrupt-parent 属性，其值为指向分发它产生的中断的设备，一般是一个中断控制器的 phandle。如果没有提供 interrupt-parent，我们假定它的 interrupt-parent 就是它的父亲。

  每个能够产生中断的设备都包含一个 interrupts 属性来描述一个或多个它的中断源。每个中断源被一个称为 interrupt specifier 的信息描述，它的格式和含义取决于**中断域**，更详细的说是依赖于它的中断域的根节点的属性。中断域根节点的 #interrupt-cells 属性用来定义表达相关的 interrupt specifier 需要多少个 u32。举例来说，对于一个 Open PIC 中断控制器，一个 interrupt specifier 用两个 u32 来描述，包括一个中断编号还有中断的 level/sense 信息。

  所谓的中断域是指解释 interrupt specifier 的上下文。中断域的根要么是一个中断控制器，要么是一个中断纽带（Nexus）。

  1. 中断控制器是一个物理设备，需要一个驱动程序去处理通过它转发的中断。它也可能被隐藏在另外一个中断域里面。中断控制器是由节点上的 interrupt-controller 属性来确定的。
  2. 中断纽带定义了两个中断域之间的转换关系。转换基于特定的域和总线的特征。这种中断域之间的转换是由 interrupt-map 属性来确定的。举个例子，一个 PCI 节点就可以视作一个定义了从 PCI 中断名字空间（INTA, INTB,...） 到一个 IRQ 控制器之间的转换的中断纽带。

  中断树的根只需进行遍历，找到一个没有 interrupts 属性且没有显式指定 interrupt-parent 的 interrupt-controller 节点即可。

* 下面是一些产生中断的设备的属性。

* (interrupts, prop-encoded-array)，数目人工确定的若干个 interrupt specifiers

  interrupts 会被 interrupts-extended 覆盖。
  
* (interrupt-parent, phandle)
  
* (interrupts-extended, phandle/prop-encoded-array)
  
  主要用于中断源连接到多个不同个中断控制器的情况，含有多个 (interrupt-parent, interrupt specifier) 的对。
  
* 下面是一些中断控制器的属性。

* (#interrupt-cells, u32)

  描述该 domain 下的 interrupt specifier 的 u32 个数。

* (interrupt-controller, empty)

* 目前看到 23 页，有空回来接着看吧。

  

  