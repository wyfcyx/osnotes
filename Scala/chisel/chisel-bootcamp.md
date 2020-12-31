binder:https://mybinder.org/v2/gh/freechipsproject/chisel-bootcamp/b6bff4acf4cec99e78e60b9be6cbc14eb6bb3c38

# Module 1: Introduction to Scala

## Variables and Constants

`val` is constant, and `var` is mutable(also can be reassigned).

## Conditionals

We should add a pair of parentheses around the condition.

> Some punctuations:
>
> () -> parentheses
>
> [] -> brackets
>
> {} -> braces
>
> , -> comma
>
> : -> colon
>
> ; -> semicolon
>
> . -> period
>
> ? -> question mark
>
> ! -> exclamation point

Sometimes we can omit the braces, for example:

```scala
if (condition)
	println("hello, world")
else
	a += 1
```

Additionally, the `else if` should start at a new line.

Like Rust, every `if` condition returns a value.

## Methods(Functions)

We use keyword `def` to define a function. It has arguments and return value, like:

```scala
def double(x: Int): Int = 2 * x
```

If the function does not require any arguments, then no side effects => no parentheses.

If the function does not have return values, then no colon.

Overloading functions: It is okay if two functions have the same names but different signatures.

Here is an example of recursive and nested functions:

```scala
/** Prints a triangle made of "X"s
  * This is another style of comment
  */
def asciiTriangle(rows: Int) {
    
    // This is cute: multiplying "X" makes a string with many copies of "X"
    def printRow(columns: Int): Unit = println("X" * columns)
    
    if(rows > 0) {
        printRow(rows)
        asciiTriangle(rows - 1) // Here is the recursive call
    }
}

// printRow(1) // This would not work, since we're calling printRow outside its scope
asciiTriangle(6)
```

## List

```scala
val x = 7
val y = 14
// Two ways to assemble a list
val list1 = List(1, 2, 3)
val list2 = x :: y :: y :: Nil
// append list2 to list1
val list3 = list1 ++ list2
// get length & size
val m = list2.length
val s = list2.size
// get first element
val head = list1.head
// get rest except the first element
val tail = list2.tail
// access by index
val v = list1(2)
```

## `for` statement

```scala
for (i <- 0 to 7) {...} // include 7, step = 1
for (i <- 0 until 7) {...} // exclude 7, step = 1
for (i <- 0 to 10 by 2) {...} // include 10, step = 2
for (v <- randomList) {...} // iterate over a list
```

## packages and imports

Package names are lower case and do not contain separators.

Common imports from `chisel3`:

```scala
// A wildcard include all classes and methods.
import chisel3._
import chisel3.iotesters.{ChiselFlatSpec, Driver, PeekPokeTester}
```

## Scala is Object Oriented 



