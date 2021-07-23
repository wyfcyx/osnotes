## basic chisel types

3 basic Chisel types: `UInt`/`SInt`/`Bool`

all chisel variables are declared as `val` (since?

``1.U`` means cast Scala ``Int(1)`` to Chisel ``UInt(1)``

two `UInt`s can add/sub/... just like ``Int``, but `UInt` and `Int` cannot add

## add, subtract and multiple

except for add, there are other operations such as subtract(`-`) and multiply(`*`)

For example, chisel code:

```scala
class MyOperators extends Module {
  val io = IO(new Bundle {
    val in      = Input(UInt(4.W))
    val out_add = Output(UInt(4.W))
    val out_sub = Output(UInt(4.W))
    val out_mul = Output(UInt(4.W))
  })

  io.out_add := 1.U + 4.U
  io.out_sub := 2.U - 1.U
  io.out_mul := 4.U * 2.U
}
println(getVerilog(new MyOperators))
```

generated verilog:

```verilog
module MyOperators(
  input        clock,
  input        reset,
  input  [3:0] io_in,
  output [3:0] io_out_add,
  output [3:0] io_out_sub,
  output [3:0] io_out_mul
);
  wire [1:0] _T_3 = 2'h2 - 2'h1; // @[cmd4.sc 10:21]
  wire [4:0] _T_4 = 3'h4 * 2'h2; // @[cmd4.sc 11:21]
  assign io_out_add = 4'h5; // @[cmd4.sc 9:21]
  assign io_out_sub = {{2'd0}, _T_3}; // @[cmd4.sc 10:21]
  assign io_out_mul = _T_4[3:0]; // @[cmd4.sc 11:14]
endmodule

```

## mux and cat

```scala
class MyOperatorsTwo extends Module {
  val io = IO(new Bundle {
    val in      = Input(UInt(4.W))
    val out_mux = Output(UInt(4.W))
    val out_cat = Output(UInt(4.W))
  })

  val s = true.B
  // Mux returns arg0 ? arg1 : arg2
  io.out_mux := Mux(s, 3.U, 0.U) // should return 3.U, since s is true
  io.out_cat := Cat(2.U, 1.U)    // concatenates 2 (b10) with 1 (b1) to give 5 (101)
}

println(getVerilog(new MyOperatorsTwo))

test(new MyOperatorsTwo) { c =>
  c.io.out_mux.expect(3.U)
  c.io.out_cat.expect(5.U)
}
println("SUCCESS!!")
```

## exercise: mac

```scala
class MAC extends Module {
  val io = IO(new Bundle {
    val in_a = Input(UInt(4.W))
    val in_b = Input(UInt(4.W))
    val in_c = Input(UInt(4.W))
    val out  = Output(UInt(8.W))
  })
  
  // write code here
  io.out := io.in_a * io.in_b + io.in_c
}

test(new MAC) { c =>
  val cycles = 100
  import scala.util.Random
  for (i <- 0 until cycles) {
    val in_a = Random.nextInt(16)
    val in_b = Random.nextInt(16)
    val in_c = Random.nextInt(16)
    c.io.in_a.poke(in_a.U)
    c.io.in_b.poke(in_b.U)
    c.io.in_c.poke(in_c.U)
    c.io.out.expect((in_a * in_b + in_c).U)
  }
}
println("SUCCESS!!")
```

## exercise: arbiter

```scala
class Arbiter extends Module {
  val io = IO(new Bundle {
    // FIFO
    val fifo_valid = Input(Bool())
    val fifo_ready = Output(Bool())
    val fifo_data  = Input(UInt(16.W))
    
    // PE0
    val pe0_valid  = Output(Bool())
    val pe0_ready  = Input(Bool())
    val pe0_data   = Output(UInt(16.W))
    
    // PE1
    val pe1_valid  = Output(Bool())
    val pe1_ready  = Input(Bool())
    val pe1_data   = Output(UInt(16.W))
  })

  io.fifo_ready := io.pe0_ready | io.pe1_ready
  io.pe0_valid := io.pe0_ready & io.fifo_valid
  io.pe1_valid := !io.pe0_valid & io.pe1_ready & io.fifo_valid
  io.pe0_data := Mut(io.pe0_valid, io.fifo_data, 0.U)
  io.pe1_data := Mut(io.pe1_valid, io.fifo_data, 0.U)
}

test(new Arbiter) { c =>
  import scala.util.Random
  val data = Random.nextInt(65536)
  c.io.fifo_data.poke(data.U)
  
  for (i <- 0 until 8) {
    // fifo_valid when 1/3/5/7
    c.io.fifo_valid.poke((((i >> 0) % 2) != 0).B)
    // pe0_ready when 2/3/6/7
    c.io.pe0_ready.poke((((i >> 1) % 2) != 0).B)
    // pe1_ready when 4/5/6/7
    c.io.pe1_ready.poke((((i >> 2) % 2) != 0).B)

    c.io.fifo_ready.expect((i > 1).B)
    c.io.pe0_valid.expect((i == 3 || i == 7).B)
    c.io.pe1_valid.expect((i == 5).B)
    
    if (i == 3 || i ==7) {
      c.io.pe0_data.expect((data).U)
    } else if (i == 5) {
      c.io.pe1_data.expect((data).U)
    }
  }
}
println("SUCCESS!!")
```

## exercise: parameterizedAdder

```scala
class ParameterizedAdder(saturate: Boolean) extends Module {
  val io = IO(new Bundle {
    val in_a = Input(UInt(4.W))
    val in_b = Input(UInt(4.W))
    val out  = Output(UInt(4.W))
  })

  val sum = io.in_a +& io.in_b

  if (saturate) {
      io.out := Mux(sum > 15.U, 15.U, sum)
  } else {
      io.out := sum
  }
}

for (saturate <- Seq(true, false)) {
  test(new ParameterizedAdder(saturate)) { c =>
    // 100 random tests
    val cycles = 100
    import scala.util.Random
    import scala.math.min
    for (i <- 0 until cycles) {
      val in_a = Random.nextInt(16)
      val in_b = Random.nextInt(16)
      c.io.in_a.poke(in_a.U)
      c.io.in_b.poke(in_b.U)
      if (saturate) {
        c.io.out.expect(min(in_a + in_b, 15).U)
      } else {
        c.io.out.expect(((in_a + in_b) % 16).U)
      }
    }
    
    // ensure we test saturation vs. truncation
    c.io.in_a.poke(15.U)
    c.io.in_b.poke(15.U)
    if (saturate) {
      c.io.out.expect(15.U)
    } else {
      c.io.out.expect(14.U)
    }
  }
}
println("SUCCESS!!")
```



