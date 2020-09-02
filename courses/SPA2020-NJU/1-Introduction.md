* 实际上是“静态程序分析”而非“软件分析”

* PL（Programming Language）国内的人才极少，都集中到 NJU

  国际上有不少活跃的研究者，计算机强校都有人做 PL

* PL 分为：理论（Theory）、环境（Environment）、应用（Application）

  理论：类型系统、语义逻辑...

  环境：编译器->指令、运行时...

  应用：可靠性、高性能...

  SPA 就属于应用分支。

* 历史发展 -> SPA 为何如此重要？

  几十年来，语言核心基本没变：分成命令式、函数式、逻辑式语言

  但是语言的应用环境，也即软件越来越复杂

  如何保证复杂软件的可靠性、安全性，成为**近期**研究的热点

* SPA 能做什么？在编译期完成：

  可靠性检查：dereference null pointer, memory leak...

  安全性检查：信息泄露、注入攻击...

  编译优化：dead code elimination, code motion...

  程序理解：比如 J 家 IDE 提供的方便功能

* Money! SPA in market

  产业界：MS/Oracle/Google 等，不做会损失钱；

  学术界：有程序就有需求！

* 对于编程的 buff

  1. 深入理解程序语法、语义
  2. 自然就能写出更可靠、安全、高效的程序

  高级程序员的自我修养（滑稽

  李老师语重心长的讲话（继续滑稽

  我觉得这跟 Rust 不谋而合啊...（看来来对了？我从未对编程语言有这样的好奇与冲动

* 什么是 SPA

  在**编译期**知道被运行程序的某些行为、性质，比如：

  * 是否有漏洞？
  * 类型安全？
  * 数据竞争？
  * 内存安全？
  * ...

* 然而，**Rice's Theorem** 告诉我们：递归可枚举语言的非平凡性质是不可判断的。

  递归可枚举 r.e. => 被图灵机接受的语言；

  非平凡性质 => 你感兴趣的，进而跟运行时行为相关的；

  不可判断 => 不存在一个能**准确**判断的方法。

* 两个重要概念：*sound* 和 *complete*

  *sound* -> overapproximate，报出来的有假的，但会比 truth 更多

  *complete* -> underapproximate，报出来的一定是真的，但会比 truth 更少

  no perfect(sound & complete), we need **useful**(compromise)

  compromise soundness -> 不 sound，也就是有些 truth 里面的 bug 报不出来；

  compromise completeness -> 不 complete，也就是报出来的某些 bug 并不在 truth 之内。

  绝大多数情况下，我们 compromise completeness，一定要 sound，也就是要**全面**，尽管会误报某些 bug

  这是因为，在编译优化、或形式化验证中，soundness 的缺失会造成整个结论的错误；因此我们需要优先保证 soundness。也就是尽可能全面，尽管有可能误报。而且，对于所有 SPA 都是越 sound 越好。

  甚至可以认为，**sound** 就代表一个正确的分析。

* 有一句话说明白 SPA？

  （打破**动态思维**）

  在确保（或尽可能接近，某些语言不存在） soundness 的情况下，做 precision（越高） 与 speed（越慢） 上的权衡，才是一个真正有用的 SPA。
  
* SPA 技术 = Abstraction + Over-Approximation（抽象 + 近似）
  
  抽象：值变成 abstract value
  
  语句近似：transfer function
  
  控制流近似：branch merging
  
  
  
  
  