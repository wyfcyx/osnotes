# Chapter1

* Level: A1

## 1.1 Sample Usage of REPL

* nice auto completion
* use command such as `:help` etc.

## 1.2 Declaring Values and Variables

* `val` means immutable while `var` show the variable is mutable

* you must initialize the variable after declaring it, otherwise an error will be encountered

* do not want to rely on the auto inference functionality of Scala? declare variable with type manually

   ```scala
   val greet: String = "Hello
   ```
   
   Hey, here comes something like Rust! And we all know there will be more!
   
* declare multiple values/variables(with the same type and initialization) at the same time
  ```scala
  var x, y = 5
  ```
  