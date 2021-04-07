## First passthrough module

```scala
// Module is built-in in Chisel, every hw module extends it
class Passthrought extends Module {
    // declare module input/output
    // it must be an instance named io of type IO 
    val io = IO(new Bundle {
        // unsigned integer of width 4
        val in = Input(UInt(4.W))
        val out = Output(UInt(4.W))
    })
    // := is a Chisel directional operator, means io.out is drived by io.in
    io.out := io.in
}
```

## elaboration

 translate chisel module to HDL

```scala
println(getVerilog(new Passthrough))
```

and the output:

```verilog
module Passthrough(
  input        clock,
  input        reset,
  input  [3:0] io_in,
  output [3:0] io_out
);
  assign io_out = io_in; // @[cmd2.sc 6:10]
endmodule
```

## module generator

```scala
class PassthroughGenerator(width: Int) extends Module {
    val io = IO(new Bundle {
        val in = Input(UInt(width.W))
        val out = Output(UInt(width.W))
    })
    io.out := io.in
}
```

elaborate it:

```scala
println(getVerilog(new PassthroughGenerator(10)))
println(getVerilog(new PassthroughGenerator(20)))
```

result:

```verilog
module PassthroughGenerator(
  input        clock,
  input        reset,
  input  [9:0] io_in,
  output [9:0] io_out
);
  assign io_out = io_in; // @[cmd5.sc 6:10]
endmodule

module PassthroughGenerator(
  input         clock,
  input         reset,
  input  [19:0] io_in,
  output [19:0] io_out
);
  assign io_out = io_in; // @[cmd5.sc 6:10]
endmodule
```

## tester

```scala
// Scala Code: `test` runs the unit test. 
// test takes a user Module and has a code block that applies pokes and expects to the 
// circuit under test (c)
test(new Passthrough()) { c =>
    c.io.in.poke(0.U)     // Set our input to value 0
    c.io.out.expect(0.U)  // Assert that the output correctly has 0
    c.io.in.poke(1.U)     // Set our input to value 1
    c.io.out.expect(1.U)  // Assert that the output correctly has 1
    c.io.in.poke(2.U)     // Set our input to value 2
    c.io.out.expect(2.U)  // Assert that the output correctly has 2
}
println("SUCCESS!!") // Scala Code: if we get here, our tests passed!
```

use ``poke`` to set input, and check output by ``expect``

``peek`` a output if you do not want to check it

> Note that the `poke` and `expect` use chisel hardware literal notation. Both operations expect literals of the correct type. If `poke`ing a `UInt()` you must supply a `UInt` literal (example: `c.io.in.poke(10.U)`, likewise if the input is a `Bool()` the `poke` would expect either `true.B` or `false.B`.

## practice

`???` means unimplemented

solution:

```scala
// Test with width 10

test(new PassthroughGenerator(10)) { c =>
    c.io.in.poke(0.U)
    c.io.out.expect(0.U)
    c.io.in.poke((1<<10-1).U)
    c.io.out.expect((1<<10-1).U)
}

// Test with width 20

test(new PassthroughGenerator(20)) { c =>
    c.io.in.poke(0.U)
    c.io.out.expect(0.U)
    c.io.in.poke((1<<20-1).U)
    c.io.out.expect((1<<20-1).U)
}

println("SUCCESS!!") // Scala Code: if we get here, our tests passed!
```

## debug

view translated firrtl

```scala
println(getFirrtl(new Passthrough))
```

```scala
Elaborating design...
Done elaborating.
;buildInfoPackage: chisel3, version: 3.4.3, scalaVersion: 2.12.12, sbtVersion: 1.3.10
circuit Passthrough : 
  module Passthrough : 
    input clock : Clock
    input reset : UInt<1>
    output io : {flip in : UInt<4>, out : UInt<4>}
    
    io.out <= io.in @[cmd2.sc 6:10]
```

