## chapter 2

## 2.2 Variables

default initialization: outside any function body->0, inside->undefined



separate compilation: compile file by file



declaration(type+name) versus definition(is a declaration, but allocate storage, possibly with initial value)

declaration which is not a definition: use the **extern** keyword

a variable can only be defined only once but can be declared multiple times



a name can be used across scopes, in different scopes it refers to different entities

explicitly refer to a global variable: `::reused`, here `::` is called a scope operator

## 2.3 Compound Types

"rvalue reference" is primarily intended used in classes, other references are lvalue references

a reference is an alias, reference cannot be rebound after it is initialized, reference can only be bound to a object

**reference is not an object**

a pointer is an **object** which can be copied and moved

`&` and `*` can be used as an operator or a part of declarator(here they are called type modifiers)

`NULL`(preprocessor, standard library defines as 0) while `nullptr` is a literal

for 2 pointers, `==` and `!=` compares the addresses they **hold**

`void *` can point to any type of objects

we should use `int *&i` rather than `int &*r`, from right to left of the variable name: firstly, it is a reference, ...

## 2.4 `const` Qualifier

constant variable shared across files: both declaration and definition should use `extern const`

reference to const: only `const T&` can reference `const T` while `T&` cannot, `const T&` cannot modify the object it refers to

initialization of a reference to const: can be from any expression that can be converted to the type of reference(sometime **temporary objects** are referenced)

example of referring temporary objects:

```c++
double dval = 3.14;
const int &ri = dval;

// in fact, compiler:
double dval = 3.14;
int temp = dval;
const int &ri = temp;
```

a reference to const can refer to a non-const object

const pointer versus pointer to const

```c++
const int *p1; // pointer to const, cannot change the object it refers to through it
int *const p2; // const pointer, cannot change the address it holds
const int *const p3; // const pointer to const 
```

top-level const(right, itself cannot be changed) versus low-level const(left, the object it refers to cannot be changed)

top-level const will be ignored when copying an object while low-level const must be considered(match or can convert to)



use `constexpr` to substitute `const` to let the compiler check whether it can be evaluated at compile time

we must use **literal types** in `constexpr`

```c++
constexpr int a = 0;
constexpr const int *p = &a;
// here constexpr->top-level const, const->low-level const
```

## 2.5 Dealing with Types

type alias:

```c++
typedef long long LL;
using LL = long long;
typedef char *pstring; // pstring->char*, but no equivalent, cannot substitute directly
```



using `auto` to let the compiler deduce the type of an expression, but not exactly the same(for example, `&`, removing top-level const)

```c++
// here f() is not called, the compiler only analyzes the type of its return value
decltype(f()) sum = x;
```

## 2.6 Defining Our Own Data Structures

