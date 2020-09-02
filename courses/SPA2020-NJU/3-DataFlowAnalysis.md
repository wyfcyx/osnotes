* 数据流分析：基础 & 重要

* data flow analysis: How data *flows* on **CFG**

  *Abstraction*: data -> application-specific data

  *safe-approximation*: flow

  CFG(program) ->  node(BB/statement), edge(control flow)

* may analysis(most in SA) -> over-approximation

  must analysis -> under-approximation，不必 sound，但必须在 truth 之内
  
  approximation 取决于 analysis
  
* Overall:
  
  different data abstraction leads to:
  
  different safe approximation leads to:
  
  different *transfer functions* and *control flow handlings*
  
* 基本概念：
  
  statement s1 transfers *in[s1]* to *out[s1]*
  
  each *in,out* is associated with a before/after *program point* of a statement
  
  DFA: give every program point a **data flow value** which contains all posible states can be observed at this point(for each variable in abstract data domain)
  
  aka: find a **solution** in *transfer function* and *control flow* constraints  
  
* transfer function cons.
  
  **forward** analysis: $out[s]=f_s(in[s])$
  
  **backward** analysis: $in[s]=f_s(out[s])$
  
* control flow cons.

  Inside a BB. $in[s_{i+1}]=out[s_i]$

  Among some BBs.

  if **forward** analysis:

   $in[B]=in[s_1],out[B]=out[s_n],out[B]=f_B(in[B])$

  $in[B]=\bigvee_{P\in\text{Predecessor(B)}}out[P]$

  $\bigvee$ is a meet operator.

  if **backward** analysis: ...
  
  [We'll back soon](https://www.bilibili.com/video/BV1oE411K79d/?spm_id_from=333.788.videocard.0)