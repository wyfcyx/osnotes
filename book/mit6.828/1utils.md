有点懒，正好也是要调研一下 MIT6.828，突然觉得做一下还挺有趣的。

# utils

这个 lab 是直接用 syscall 或是封装好的用户库里面的实用功能写用户态程序。

系统调用链的话，在 `user/user.h` 中能够看到：

```c
int sleep(int);
```

这个函数是用汇编实现的，在 `user/usys.S` 中：

```c
.global sleep
sleep:
 li a7, SYS_sleep
 ecall
 ret
```

至于 `SYS_sleep` 这个 syscall ID 是在 `kernel/syscall.h` 中定义的。

## lab:sleep

```c
#include "kernel/types.h"
#include "kernel/stat.h"
#include "user/user.h"

int
main(int argc, char *argv[])
{
  sleep(atoi(argv[1]));
  exit(0);
}
```

别忘了在 Makefile 的 `UPROGS` 下面加上这个程序。

然后 `./grade-lab-util sleep` 看一下是否通过。

## lab:pingpong

```c
#include "kernel/types.h"
#include "kernel/stat.h"
#include "user/user.h"

static char TO_CHILD = 'A';
static char TO_PARENT = 'B';
int
main(int argc, char *argv[])
{
    int pid, pipe_to_child[2], pipe_to_parent[2];
    pipe(pipe_to_child);
    pipe(pipe_to_parent);
    pid = fork();
    if (pid == 0) {
        // child process
        char c;
        read(pipe_to_child[0], &c, 1);
        if (c == TO_CHILD)
            fprintf(1, "%d: received ping\n", getpid());
        write(pipe_to_parent[1], &TO_PARENT, 1);
    } else {
        // parent process
        char c;
        write(pipe_to_child[1], &TO_CHILD, 1);
        read(pipe_to_parent[0], &c, 1);
        if (c == TO_PARENT)
            fprintf(1, "%d: received pong\n", getpid());
    }
    exit(0);
}
```

这里的坑在于我们必须开两个 pipe，这里的 pipe 是一个单向通道。我们暂时不管它内部是怎么实现的吧。

## lab:primes

wait 系统调用的功能是等待一个子进程结束，并以指针的方式得到它的返回值。如果当前进程没有任何子进程则会立即返回 -1 。

折腾了挺长时间终于做出来了。

坑1：管道也是基于引用计数的，当你想关闭一个管道的写端的时候，必须所有进程都将这个 fd close 时才能成功。由于 pipe 是个单向通道，我们必须在 fork 之后就立即 close 双方不会用到的 fd，这应该是常规操作了？

坑2：xv6 里面好像同时只支持 7 个 Pipe，这超过了 35 以内的质数数量。所以发现 $p>\sqrt{\text{MAX}}$ 的时候，也就是只剩下质数的时候，就可以直接输出不用再 fork 了。

核心思路是通过一个 while 循环，如果 fork 出来是子进程的话，continue 回到循环开头。

```c
#include "kernel/types.h"
#include "kernel/stat.h"
#include "user/user.h"

#define MAX 35
int
main(int argc, char *argv[])
{
    int pipe0[2], pipe1[2], i;
    pipe(pipe1);
    if (fork() > 0) {
        close(pipe1[0]);
        for (i = 2; i <= MAX; ++i) {
            write(pipe1[1], &i, 4);
        }
        close(pipe1[1]);
        wait(0);
        exit(0);
    } else {
        while (1) {
            pipe0[0] = pipe1[0];
            pipe0[1] = pipe1[1];
            close(pipe0[1]);
            int p, n;
            if (read(pipe0[0], &p, 4) == 0) {
                close(pipe0[0]);
                exit(0);
            }
            fprintf(1, "prime %d\n", p, getpid());
            if (p * p > MAX) {
                while (read(pipe0[0], &n, 4) != 0) {
                    fprintf(1, "prime %d\n", n, getpid());
                }
                close(pipe0[0]);
                exit(0);
            }
            pipe(pipe1);
            int pid = fork();
            if (pid == 0)
                continue;
            close(pipe1[0]);
            while (read(pipe0[0], &n, 4) != 0) {
                if (n % p != 0) {
                    write(pipe1[1], &n, 4);
                }
            }
            close(pipe0[0]);
            close(pipe1[1]);
            wait(0);
            exit(0);
        }
    }
}
```

## lab:find

```c
#include "kernel/types.h"
#include "kernel/stat.h"
#include "kernel/fs.h"
#include "user/user.h"

void find(char *path, char *file) {
    char buf[512], *p;
    int fd;
    struct dirent de;
    struct stat st;

    if ((fd = open(path, 0)) < 0) {
        fprintf(2, "find: cannot open %s\n", path);
        return;
    }
    if (fstat(fd, &st) < 0) {
        fprintf(2, "find: cannot stat %s\n", path);
        close(fd);
        return;
    }
    if (st.type == T_FILE) {
        fprintf(2, "find: %s is not a path\n", path);
        close(fd);
        return;
    }

    strcpy(buf, path);
    p = buf + strlen(path);
    *p++ = '/';
    //fprintf(2, "buf = %s\n", buf);
    while (read(fd, &de, sizeof(de)) == sizeof(de)) {
        if (de.inum == 0)
            continue;
        if (strcmp(de.name, ".") == 0)
            continue;
        if (strcmp(de.name, "..") == 0)
            continue;
        int len = strlen(de.name);
        memmove(p, de.name, DIRSIZ);
        p[len] = 0;
        //fprintf(2, "found dirent %s\n", buf);
        if (stat(buf, &st) < 0) {
            printf("find: cannot stat %s\n", buf);
            continue;
        }
        if (st.type == T_FILE) {
            if (strcmp(de.name, file) == 0) {
                fprintf(1, "%s\n", buf, de.name);
            }
        } else if (st.type == T_DIR) {
            find(buf, file);
        }
    }
    close(fd);
}

int main(int argc, char *argv[]) {
    find(argv[1], argv[2]);
    exit(0);
}
```

fs 的具体架构等做到了相应的 lab 的时候再说，简单整理一下相应的 syscall。

`open` 可以根据设置的 flag 打开路径对应文件，并返回其 fd，`close` 则是为当前进程关闭文件。

`fstat` 可以获取路径对应文件的元数据，目前内容是：

```c
#define T_DIR     1   // Directory
#define T_FILE    2   // File
#define T_DEVICE  3   // Device

struct stat {
  int dev;     // File system's disk device
  uint ino;    // Inode number
  short type;  // Type of file
  short nlink; // Number of links to file
  uint64 size; // Size of file in bytes
};
```

我们可以根据它来确定类型是文件还是目录。

`read` 可以读一个 fd，根据 fd 类型不同读取的区域不一样。随着读取会更新当前进程读 fd 的 offset。

目录的数据布局是一个大 `dirent` 数组，每个 `dirent` 代表一个子文件或子目录，内含名字和 Inode 编号。

```c
struct dirent {
  ushort inum;
  char name[DIRSIZ];
};
```

利用上面这些 syscall 参考 ls 就很容易完成这道题目了。

## lab:xargs

```c
#include "kernel/types.h"
#include "kernel/stat.h"
#include "user/user.h"
#include "kernel/fs.h"
#include "kernel/param.h"

int main(int argc, char *argv[]) {
    char buf[512], c;
    int len = 0;
    while (1) {
        if (read(0, &c, 1) == 0)
            break;
        buf[len++] = c;
        if (c == '\n') {
            buf[len - 1] = '\0';
            len = 0;
            if (fork() == 0) {
                char* tmp_argv[MAXARG];
                memcpy(tmp_argv, argv + 1, (argc - 1) * sizeof((char*)0));
                tmp_argv[argc - 1] = buf;
                exec(argv[1], tmp_argv);
            } else {
                wait(0);
            }
        }
    }
    exit(0);
}
```

坑1：之前一直以为 xv6 里面 1 是标准输入，2是标准输出...但实际上它是根据标准来的，012 分别是标准输入、标准输出和标准错误输出。之前我把所有东西都输出到标准错误输出了，但是测试脚本看不出来它有问题...现在把弄错的地方都改过来了。

知识：如果输出 `./f a b c d` ，则进入程序 `f` 之后 argc = 5，它们分别是 `./f, a, b, c, d`。

坑2：传给 grep 的时候要把文件末尾的换行符去掉。其 ASCII 码应该是 10。



