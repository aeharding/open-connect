/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Flush one existing file or directory; report syscall failures.
 * Caller owns path/type/identity validation and the operation deadline.
 * ARM build uses the Linux 3.0 ARM EABI directly, without a target libc.
 */
#ifdef OC_HOST
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>

static long open_readonly(const char *path, int directory) {
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK |
                       (directory ? O_DIRECTORY : 0));
    return fd < 0 ? -errno : fd;
}
static long flush_fd(int fd) { return fsync(fd) < 0 ? -errno : 0; }
static long close_fd(int fd) { return close(fd) < 0 ? -errno : 0; }
static void report(const char *s, unsigned n) { (void)write(2, s, n); }
#else
#if !defined(__arm__) || !defined(__ARM_EABI__)
#error "Target build requires 32-bit ARM EABI"
#endif
/* Linux v3.0 arch/arm/include/asm/{unistd,fcntl}.h and asm-generic/fcntl.h. */
static long syscall3(long number, long a, long b, long c) {
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r7 __asm__("r7") = number;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r7) : "memory", "cc");
    return r0;
}
static long open_readonly(const char *path, int directory) {
    return syscall3(5, (long)path, 0100000 | 04000 | (directory ? 040000 : 0), 0);
}
static long flush_fd(int fd) { return syscall3(118, fd, 0, 0); }
static long close_fd(int fd) { return syscall3(6, fd, 0, 0); }
static void report(const char *s, unsigned n) { (void)syscall3(4, 2, (long)s, n); }
#endif

static int failure(long error) {
    /* Exit status carries errno when it fits. Diagnostics name the failed call. */
    return error < 0 && error >= -125 ? (int)-error : 125;
}

static int run(int argc, char **argv) {
    if (argc != 3 || !argv[1][0] || argv[1][1] ||
        (argv[1][0] != 'f' && argv[1][0] != 'd') || argv[2][0] != '/') {
        report("usage: flush f|d /absolute/path\n", 32);
        return 64;
    }
    long fd = open_readonly(argv[2], argv[1][0] == 'd');
    if (fd < 0) {
        report("open failed\n", 12);
        return failure(fd);
    }
    long flushed = flush_fd((int)fd);
    long closed = close_fd((int)fd);
    if (flushed < 0) {
        report("fsync failed\n", 13);
        return failure(flushed);
    }
    if (closed < 0) {
        report("close failed\n", 13);
        return failure(closed);
    }
    return 0;
}

#ifdef OC_HOST
int main(int argc, char **argv) { return run(argc, argv); }
#else
int entry(unsigned *stack) { return run((int)stack[0], (char **)(stack + 1)); }
__asm__(".text\n.global _start\n.type _start,%function\n"
        "_start:\nmov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
