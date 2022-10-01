# 4. Expressions

## 4.11 Type Conversions

implicit conversions

* arithmetic conversions: preserving precision

* conversion to const
* conversions defined by class types

explicit conversions

* named casts: `cast-name<type>(expression)`
  * `static_cast`
  * `dynamic_cast`
  * `const_cast`: changing `const`ness, used in overloading functions
  * `reinterpret_cast`: reinterpreting bits, dangerous, machine-dependent
* old-style casts: `type(expr)` or `(type) expr`

