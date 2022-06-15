## Item 1: Use the type system to express your data structures

if caller want to handle the possible failure: `char::from_u32` versus `char::from_u32_unchecked`

## Item 2: Use the type system to express common behavior

function pointers `fn` like `fn(i32, i32) -> i32` implements `Copy, Eq, std::fmt::Pointer`

closures: we can carry data other than arguments,
