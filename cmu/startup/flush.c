/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Flush/hash one existing file, flush a directory, or link without replacement.
 * Report syscall failures; never interpret a link destination as a directory.
 * Caller owns path/type/identity validation and the operation deadline.
 * ARM build uses the Linux 3.0 ARM EABI directly, without a target libc.
 */
#include "../installer/boot-hash.h"
#ifdef OC_HOST
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

static long open_readonly(const char *path, int directory) {
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK |
                       (directory ? O_DIRECTORY : 0));
    return fd < 0 ? -errno : fd;
}
static long flush_fd(int fd) { return fsync(fd) < 0 ? -errno : 0; }
static long close_fd(int fd) { return close(fd) < 0 ? -errno : 0; }
static long regular_fd(int fd) {
    struct stat s;
    if (fstat(fd, &s) < 0) return -errno;
    return S_ISREG(s.st_mode) ? 0 : -EINVAL;
}
static long read_fd(int fd, void *p, unsigned n) {
    long r = read(fd, p, n);
    return r < 0 ? -errno : r;
}
static long output(const void *p, unsigned n) {
    long r = write(1, p, n);
    return r < 0 ? -errno : r;
}
static long link_path(const char *source, const char *target) {
    return linkat(AT_FDCWD, source, AT_FDCWD, target, 0) < 0 ? -errno : 0;
}
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
    return syscall3(5, (long)path, 0100000 | 04000 | (directory ? 040000 : 0400000), 0);
}
static long flush_fd(int fd) { return syscall3(118, fd, 0, 0); }
static long close_fd(int fd) { return syscall3(6, fd, 0, 0); }
static long regular_fd(int fd) {
    /* ARM EABI stat64: 104 bytes, 8-byte alignment, mode at byte 16.
     * Same Linux v3.0 layout as boot-io.h; no other metadata is needed here. */
    union { oc_u64 align; oc_u32 words[26]; } s;
    _Static_assert(sizeof(s) == 104, "ARM stat64 layout");
    long r = syscall3(197, fd, (long)&s, 0);
    return r < 0 ? r : ((s.words[4] & 0170000) == 0100000 ? 0 : -22);
}
static long read_fd(int fd, void *p, unsigned n) { return syscall3(3, fd, (long)p, n); }
static long output(const void *p, unsigned n) { return syscall3(4, 1, (long)p, n); }
static long link_path(const char *source, const char *target) {
    return syscall3(9, (long)source, (long)target, 0);
}
static void report(const char *s, unsigned n) { (void)syscall3(4, 2, (long)s, n); }
#endif

static int failure(long error) {
    /* Exit status carries errno when it fits. Diagnostics name the failed call. */
    return error < 0 && error >= -125 ? (int)-error : 125;
}

/* Keep hash scratch out of the existing f/d/l modes' stack frames. */
static __attribute__((noinline)) int hash_path(const char *path) {
    long fd, result, closed;
    do { fd = open_readonly(path, 0); } while (fd == -4);
    if (fd < 0) {
        report("open failed\n", 12);
        return failure(fd);
    }
    do { result = regular_fd((int)fd); } while (result == -4);
    OcHash hash;
    oc_u8 buffer[512];
    char digest[65];
    oc_hash_init(&hash);
    while (result >= 0) {
        result = read_fd((int)fd, buffer, sizeof buffer);
        if (result == -4) { result = 0; continue; }
        if (result <= 0) break;
        oc_hash_add(&hash, buffer, (unsigned)result);
    }
    closed = close_fd((int)fd);
    if (result < 0 || closed < 0) {
        report("hash failed\n", 12);
        return failure(result < 0 ? result : closed);
    }
    oc_hash_finish(&hash, digest);
    digest[64] = '\n';
    for (unsigned used = 0; used < sizeof digest;) {
        result = output(digest + used, sizeof digest - used);
        if (result == -4) continue;
        if (result <= 0) {
            report("write failed\n", 13);
            return failure(result < 0 ? result : -5);
        }
        used += (unsigned)result;
    }
    return 0;
}

static int run(int argc, char **argv) {
    /* Hash accepts relative paths too, matching the shell's former < "$1". */
    if (argc == 3 && argv[1][0] == 'h' && !argv[1][1]) return hash_path(argv[2]);
    if (argc == 4 && argv[1][0] == 'l' && !argv[1][1] &&
        argv[2][0] == '/' && argv[3][0] == '/') {
        long linked = link_path(argv[2], argv[3]);
        if (linked < 0) {
            report("link failed\n", 12);
            return failure(linked);
        }
        return 0;
    }
    if (argc != 3 || !argv[1][0] || argv[1][1] ||
        (argv[1][0] != 'f' && argv[1][0] != 'd') || argv[2][0] != '/') {
        static const char usage[] = "usage: flush f|d /absolute/path\n"
                                    "       flush l /absolute/source /absolute/target\n"
                                    "       flush h path\n";
        report(usage, sizeof usage - 1);
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
