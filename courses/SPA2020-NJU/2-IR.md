* 利于 SPA 算法设计的 IR 表示

  没有准确的定义，什么好用就用什么

* 编译器回顾

  词法分析 Lexical Analysis，基于正则表达式，生成 tokens

  语法分析 Syntax Analysis，基于上下文无关语法，生成抽象语法树 AST

  语义检查 Semantic Analysis，基于 Attribute Grammar，生成 Decorated AST

  通过 Translator 转化为 IR（通常是三地址码），以 IR 为界限划分编译器前后端

  对指定平台生成指令

* SPA 基于三地址码（3AC）进行，不能基于 source code，因为...

  那么为什么不基于 AST 呢？

  3AC 的优点：贴近汇编、语言**无关**（支持不同的前端）、更加简洁紧凑、包含**控制流**信息（AST 上很难被看出来）

  因此，基于 3AC 更方便 SPA

* 3AC：每条指令仅包含 3 个“地址”：变量、常数、编译器临时变量

  右边只能有一个操作符

  常见的 3AC：

  x = y bop z; x = uop y; x = y; goto L; if x goto L; if x rop y goto L;

  bop -> 二元运算符； uop -> 一元运算符； rop -> 关系运算符。

* Soot 采用的 IR: Jimple——Typed 3AC

* JVM 支持 4 种调用

  invoke special: call constrcutor, call superclass methods, call private methods

  invoke virtual: instance methods call(virtual dispatch)

  invoke interface

  invoke static: call static methods

  Java 7: invoke dynamic，在 JVM 跑 dynamic 语言

* Static Single Assignment(SSA)

  相比 3AC，变量的每一次重新声明被给予一个新的下标，被视为一个不同的变量

  在 merge 的时候通过 phi 函数进行合并

  优点：带有一些流信息，相同时间开销带来额外的精度；

  缺点：变量、phi 函数太多。

* 3AC -> CFG(Control Flow Graph，控制流图)

  单位：单条指令或 BB(Basic Block，基本块)

* 基本块定义：控制流只能从第一条指令进入，只能从最后一条指令退出的极大连续指令块

  找出所有的 BB：只需确定所有的入口，当某条指令可以被直接跳转过来或者上一条指令跳转到别的地方它就是一个入口
  
* 根据 BB 建立 CFG：

  1. 若块 A 的最后一条指令跳转到块 B，加入有向边 A->B
  2. 若块 B follow 块 A，且块 A 的最后一条指令不是无条件跳转，加入有向边 A->B
  3. 对跳转指令中的 label 进行重命名为块的名字

  若存在 A->B ，称 A 是 B 的前驱，B 是 A 的后继

  此外，还需要加入两个无实际意义、方便算法描述的 BB，即 Entry 和 Exit

* 所以 3AC 转化成的 CFG 才是 SA 需要的东西