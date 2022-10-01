# 6. Functions

## 6.1 Function Basics

a local static object is initialized before it is accessed for the first time

## 6.2 Argument Passing

`const` parameters: top-level const

`const T` and `T` do not differ in function argument declaration(since top-level const is ignored)

a varying number of arguments of the same type: `initializer_list<T>`

`varargs`, communicating with C, ellipsis arguments

## 6.3 Return Types and the `return` Statement

implicit conversion on a return statement

a possible UB: function exits without any return, and it compiles

calls to functions which return references are lvalue, other calls are rvalue

list initializing the return value: `return {"a", "b", "c"};` a `vector<string>`

## 6.4 Overloaded Functions

low-level const and non-const references or pointers differ when they are used in overloaded function parameters

the compiler prefers the non-const version

## 6.5 Features for specialized uses

default function arguments: must be a suffix of the argument list; when calling, provide a prefix

inline functions: insert assembly in place where the function is called. However, compiler can ignore this request to its own discretion.

assert: preprocessor macro

`NDEBUG` preprocessor variable: use `-D NDEBUG` or `#define NDEBUG` to turn off debugging behaviors

other useful variables provided by the compiler: `__func__, __FILE__, __LINE__, __TIME__, __DATE__`

## 6.6 Function Matching

skipped since it's not important

## 6.7 Pointers to Functions

substituting function name

```c++
bool lengthCompare(const string &, const string &);
bool (*pf)(const string &, const string &); //uninitialized
```



 
