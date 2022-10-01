# 7. Classes

fundamental idea behind classes: data abstraction(separation of interface and implementation) and encapsulation

## 7.1 Defining Abstract Data Types

abstract data type: users cannot directly access the data members

const member functions: put a const after the argument list

default constructors:

* compiler generated: synthesized default constructor(in-class initializer or default initialized), only if we do not define any other constructors

other operations: copy, assignment, destroy

## 7.2 Access Control and Encapsulation

`public:` and `private:` specifier

difference between `class` and `struct`: default access level(private versus public)

friend: allow another class or function access non-public member of a class, the `friend` keyword is only used in the declaration inside the class

## 7.3 Additional Class Features

mutable data members: can be modified even in const member functions

## 7.4 Class Scopes

not important

## 7.5 Constructors Revisited

members are initialized in the order they appear in the class definition

delegating constructors

exhausted...

## 7.6 `static` Class Members

objects can also use static class members

do not need to repeat `static` keyword outside the class

(non-const) static class members should not be initialized inside the class