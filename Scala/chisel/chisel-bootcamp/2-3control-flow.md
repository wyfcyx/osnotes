## last connect

we can use `:=` to assign values to a wire multiple times but only the last one is effective

## when, elsewhen and otherwise

they are provided by Chisel

when(like if) -> elsewhen*(like elseif) -> otherwise+(like else)

unlike if block, `when` is not an expression, so it cannot return a value

the type of the argument it takes is `Bool` in Chisel, we can use logical operators such as `!, &&, ||`

## the `Wire` construct

`wire` can appear both left and right side of operator `:=`

```scala
// declare a new Wire
val row10 = Wire(UInt(16.W))
```

an exhaustive tester:

```scala
test(new Sort4) { c => 
    List(1, 2, 3, 4).permutations.foreach { case i0 :: i1 :: i2 :: i3 :: Nil => 
        ...
    }
}
```

## Exercise: Polynomial Circuit

sanity check in pure Scala

```scala
def poly0(x: Int): Int = x * x - 2 * x + 1
def poly1(x: Int): Int = 2 * x * x + 6 * x + 3
def poly2(x: Int): Int = 4 * x * x - 10 * x - 5

assert(poly0(0) == 1)
assert(poly1(0) == 3)
assert(poly2(0) == -5)

assert(poly0(1) == 0)
assert(poly1(1) == 11)
assert(poly2(1) == -11)
```

using if

```scala
def poly(select: Int, x: Int): Int = {
  if (select == 0) {
      x*x-2*x+1
  } else if (select == 1) {
      2*x*x+6*x+3
  } else {
      4*x*x-10*x-5
  }
}

assert(poly(1, 0) == 3)
assert(poly(1, 1) == 11)
assert(poly(2, 1) == -11)
```

full polynomial circuit

```scala
// compute the polynomial
class Polynomial extends Module {
  val io = IO(new Bundle {
    val select = Input(UInt(2.W))
    val x = Input(SInt(32.W))
    val fOfX = Output(SInt(32.W))
  })
    
  val result = Wire(SInt(32.W))  
  val square = Wire(SInt(32.W))  
  
  square := io.x * io.x
  
  // mention that we should use operator '===' to check the equality of two values of chisel built-in type
  when (io.select === 0.U) {
      result := square-2.S*io.x+1.S
  }.elsewhen (io.select === 1.U) {
      result := 2.S*square+6.S*io.x+3.S
  }.otherwise {
      result := 4.S*square-10.S*io.x-5.S
  }

  io.fOfX := result  
}

// Test Polynomial
test(new Polynomial) { c =>
  for(x <- 0 to 20) {
    for(select <- 0 to 2) {
      c.io.select.poke(select.U)
      c.io.x.poke(x.S)
      c.io.fOfX.expect(poly(select, x).S)
    }
  }
}
println("SUCCESS!!") // Scala Code: if we get here, our tests passed!
```

## Exercise: FSM

sanity check

```scala
// state map
def states = Map("idle" -> 0, "coding" -> 1, "writing" -> 2, "grad" -> 3)

// life is full of question marks
def gradLife (state: Int, coffee: Boolean, idea: Boolean, pressure: Boolean): Int = {
  var nextState = states("idle")
  if (coffee) {
      if (state == states("idle") || state == states("coding")) {
          nextState = states("coding")
      } else if (state == states("writing")) {
          nextState = states("writing")
      } else if (state == states("grad")) {
          nextState = states("idle")
      }
      /*
      // this cannot compile since only static value is allowed
      nextState = state match {
          case states("idle") | states("coding") => states("coding")
          case states("writing") => states("writing")
          case states("grad") => states("idle")
      }
      */
  } else if (idea) {
      if (state == states("idle")) {
          nextState = states("idle")
      } else if (state == states("coding") || state == states("writing")) {
          nextState = states("writing")
      } else if (state == states("grad")) {
          nextState = states("idle")
      }
  } else if (pressure) {
      if (state == states("idle") || state == states("coding")) {
          nextState = states("writing")
      } else if (state == states("writing")) {
          nextState = states("grad")
      } else if (state == states("grad")) {
          nextState = states("idle")
      }
  }
  nextState
}

// some sanity checks
(0 until states.size).foreach{ state => assert(gradLife(state, false, false, false) == states("idle")) }
assert(gradLife(states("writing"), true, false, true) == states("writing"))
assert(gradLife(states("idle"), true, true, true) == states("coding"))
assert(gradLife(states("idle"), false, true, true) == states("idle"))
assert(gradLife(states("grad"), false, false, false) == states("idle"))
```

chisel code

```scala
// life gets hard-er
class GradLife extends Module {
  val io = IO(new Bundle {
    val state = Input(UInt(2.W))
    val coffee = Input(Bool())
    val idea = Input(Bool())
    val pressure = Input(Bool())
    val nextState = Output(UInt(2.W))
  })
    
  val idle :: coding :: writing :: grad :: Nil = Enum(4)
  
  when (io.coffee) {
      when (io.state === idle || io.state === coding) {
          io.nextState := coding
      }.elsewhen (io.state === writing) {
          io.nextState := writing
      }.otherwise {
          io.nextState := idle
      }
  }.elsewhen (io.idea) {
      when (io.state === idle) {
          io.nextState := idle
      }.elsewhen (io.state === coding || io.state === writing) {
          io.nextState := writing
      }.otherwise {
          io.nextState := idle
      }
  }.elsewhen (io.pressure) {
      when (io.state === idle || io.state === coding) {
          io.nextState := writing
      }.elsewhen (io.state === writing) {
          io.nextState := grad
      }.otherwise {
          io.nextState := idle
      }
  }.otherwise {
      io.nextState := idle
  }
}


// Test
test(new GradLife) { c =>
  // verify that the hardware matches the golden model
  for (state <- 0 to 3) {
    for (coffee <- List(true, false)) {
      for (idea <- List(true, false)) {
        for (pressure <- List(true, false)) {
          c.io.state.poke(state.U)
          c.io.coffee.poke(coffee.B)
          c.io.idea.poke(idea.B)
          c.io.pressure.poke(pressure.B)
          c.io.nextState.expect(gradLife(state, coffee, idea, pressure).U)
        }
      }
    }
  }
}
println("SUCCESS!!") // Scala Code: if we get here, our tests passed!
```



