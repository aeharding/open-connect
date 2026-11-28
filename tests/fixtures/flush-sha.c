/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Host-only syscall faults around the actual helper. No target test hooks.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int fault_open(const char *, int, ...);
static int fault_stat(int, struct stat *);
static ssize_t fault_read(int, void *, size_t);
static ssize_t fault_write(int, const void *, size_t);
static int fault_close(int);
#define open fault_open
#define fstat fault_stat
#define read fault_read
#define write fault_write
#define close fault_close
#include "../../cmu/startup/flush.c"
#undef open
#undef fstat
#undef read
#undef write
#undef close

static int fault(const char *name) {
    const char *selected = getenv("OC_FLUSH_FAULT");
    return selected && !strcmp(selected, name);
}
static int fault_open(const char *path, int flags, ...) {
    static int calls;
    if (++calls == 1 && fault("open-eintr")) { errno = EINTR; return -1; }
    return open(path, flags);
}
static int fault_stat(int fd, struct stat *s) {
    static int calls;
    if (++calls == 1 && fault("stat-eintr")) { errno = EINTR; return -1; }
    if (fault("stat-error")) { errno = EIO; return -1; }
    return fstat(fd, s);
}
static ssize_t fault_read(int fd, void *p, size_t n) {
    static int calls;
    ++calls;
    if (calls % 2 && fault("read-eintr")) { errno = EINTR; return -1; }
    if (calls == 2 && fault("read-error")) { errno = EIO; return -1; }
    if (fault("short-read") && n > 7) n = 7;
    return read(fd, p, n);
}
static ssize_t fault_write(int fd, const void *p, size_t n) {
    static int calls;
    if (fd == 1) {
        if (++calls == 1 && fault("write-eintr")) { errno = EINTR; return -1; }
        if (fault("write-error")) { errno = EIO; return -1; }
        if (fault("write-zero")) return 0;
        if (fault("short-write") && n > 7) n = 7;
    }
    return write(fd, p, n);
}
static int fault_close(int fd) {
    static int calls;
    ++calls;
    int r = close(fd);
    if (fault("close-error")) { errno = EIO; return -1; }
    if (fault("close-eintr")) {
        if (calls > 1) { errno = EBADF; return -1; }
        errno = EINTR;
        return -1;
    }
    return r;
}
