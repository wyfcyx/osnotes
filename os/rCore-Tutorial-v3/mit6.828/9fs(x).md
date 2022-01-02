# fs

## lab: large files

将 singly-indirect 改成 doubly-indirect，从而将一个 inode 也就是一个文件支持的数据大小从 256+12 个块（13 个块里面有 12 个直接指向数据块，1个指向 1 级索引块）变成 256*256+256+11 个块（11 个直接指向数据块，1个指向 1 级索引块，1个指向 2 级索引块）。

## lab: symbolic links

实现一个新的 syscall `symlink(char *target, char *path)`，在 `path` 处创建一个指向 `target` 的符号链接，文件类型为 `T_SYMLINK`，将 `target` 保存在文件 `path` 的 data block 内。当用特定的 flag `open` 一个符号链接的时候，会转化为 `open` 符号链接指向的文件，如果它仍然是一个符号链接，就不断转化下去直到不是一个符号链接。注意符号链接和链接系列 syscall `link/unlink` 不冲突。 