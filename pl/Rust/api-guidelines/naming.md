| perfix  |   cost    |                          ownership                           |
| :-----: | :-------: | :----------------------------------------------------------: |
|  `as_`  |   free    |                      borrowed->borrowed                      |
|  `to_`  | expensive | borrowed->borrowed; borrowed->owned(non-copy); owned->owned(copy) |
| `into_` | variable  |                    owned->owned(non-copy)                    |

`as_` and `into_` decrease abstraction and get a representation at a lower level, which `to_` keeps the level of abstraction.

`into_inner` works as an unwrapper.

`as_mut_slice` is over `as_slice_mut` since `mut_slice` is a complete type.