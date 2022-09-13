# 3 Strings, Vectors and Arrays

## 3.1 Namespace `using` declarations

headers should not include `using` declarations such as `using std::cin`

## 3.2 Library `string` type

one way of initialization `string(n, c)`

literal initialization: do not include null character at the end

`getline(istream, s)`, return the input stream, not including the newline

`while (cin >> s)`, until end of file

`#include <cctype>` includes `isdigit, isalpha` and so on

iterate by value(copy required) `for (auto c: s)`; iterate by reference `for (auto& c: s)`

## 3.3 Library `vector` type

`vector` is a **class template** and it is also referred to as a **container**

safety: do not change a vector's size in a range loop of it

## 3.4 Introducing Iterators

`*iter` returns a **reference** to the element

type of iterators: `string::iterator` or `string::const_iterator`, but we may want to use `auto` instead

```c++
for (auto it = s.begin(); it != s.end(); ++it) { ... }
```

`cbegin()` and `cend` returns `const_iterator`

`vector` and `string` iterators support iterator arithmetic: +n, -n, `it1-it2`, <, <=, ...

## 3.5 Arrays

