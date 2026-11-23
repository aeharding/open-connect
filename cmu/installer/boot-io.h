/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Small host/CMU adapter; target uses Linux 3.0 ARM EABI without target libc.
 * ABI references (numeric interfaces and layout, not copied implementation):
 * https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/stat.h
 * https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/unistd.h
 * https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/fcntl.h
 */
#ifndef OC_BOOT_IO_H
#define OC_BOOT_IO_H
#include "boot-hash.h"

enum { OC_READ=0, OC_WRITE=1, OC_RW=2, OC_DIRECTORY=4, OC_CREATE=8, OC_EXCLUSIVE=16 };
enum { OC_REGULAR=0100000, OC_DIR=0040000, OC_TYPE=0170000 };
enum { OC_COPY_SOURCE=0, OC_COPY_OK=1, OC_COPY_DEST=-1 };
typedef struct {
    oc_u64 device, inode, size, modified, changed;
    oc_u32 mode, uid, gid, modified_ns, changed_ns;
} OcMeta;

#ifdef OC_HOST
#include <errno.h>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#define OC_CWD AT_FDCWD
static long oc_openat(int parent, const char *path, unsigned options, unsigned mode) {
    int flags=O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC;
    flags|=(options&OC_RW)?O_RDWR:((options&OC_WRITE)?O_WRONLY:O_RDONLY);
    if (options&OC_DIRECTORY) flags|=O_DIRECTORY;
    if (options&OC_CREATE) flags|=O_CREAT;
    if (options&OC_EXCLUSIVE) flags|=O_EXCL;
    int fd=openat(parent,path,flags,mode);
    return fd<0?-errno:fd;
}
static long oc_read(int fd, void *p, unsigned n) { long r=read(fd,p,n); return r<0?-errno:r; }
static long oc_write(int fd, const void *p, unsigned n) { long r=write(fd,p,n); return r<0?-errno:r; }
static long oc_close(int fd) { return close(fd)<0?-errno:0; }
static long oc_sync(int fd) { return fsync(fd)<0?-errno:0; }
static long oc_metadata(int fd, const char *path, OcMeta *m) {
    struct stat s;
    if ((path?fstatat(fd,path,&s,AT_SYMLINK_NOFOLLOW):fstat(fd,&s))<0) return -errno;
    if (s.st_size<0) return -22;
    m->device=s.st_dev; m->inode=s.st_ino; m->size=(oc_u64)s.st_size;
    m->mode=s.st_mode; m->uid=s.st_uid; m->gid=s.st_gid;
#ifdef __APPLE__
    m->modified=s.st_mtimespec.tv_sec; m->modified_ns=s.st_mtimespec.tv_nsec;
    m->changed=s.st_ctimespec.tv_sec; m->changed_ns=s.st_ctimespec.tv_nsec;
#else
    m->modified=s.st_mtim.tv_sec; m->modified_ns=s.st_mtim.tv_nsec;
    m->changed=s.st_ctim.tv_sec; m->changed_ns=s.st_ctim.tv_nsec;
#endif
    return 0;
}
#else
#define OC_CWD (-100)
#if !defined(__arm__) || !defined(__ARM_EABI__)
#error "Target requires 32-bit ARM EABI"
#endif
static long oc_syscall4(long number, long a, long b, long c, long d) {
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    register long r3 __asm__("r3")=d;
    register long r7 __asm__("r7")=number;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r7) : "memory","cc");
    return r0;
}
static long oc_openat(int parent, const char *path, unsigned options, unsigned mode) {
    unsigned flags=0100000|04000|0400000|02000000; /* ARM NOFOLLOW/NONBLOCK/LARGEFILE/CLOEXEC */
    flags|=(options&OC_RW)?2:((options&OC_WRITE)?1:0);
    if (options&OC_DIRECTORY) flags|=040000;
    if (options&OC_CREATE) flags|=0100;
    if (options&OC_EXCLUSIVE) flags|=0200;
    return oc_syscall4(322,parent,(long)path,flags,mode);
}
static long oc_read(int fd, void *p, unsigned n) { return oc_syscall4(3,fd,(long)p,n,0); }
static long oc_write(int fd, const void *p, unsigned n) { return oc_syscall4(4,fd,(long)p,n,0); }
static long oc_close(int fd) { return oc_syscall4(6,fd,0,0,0); }
static long oc_sync(int fd) { return oc_syscall4(118,fd,0,0,0); }
static long oc_metadata(int fd, const char *path, OcMeta *m) {
    /* ARM EABI stat64 has 8-byte alignment, size 104; the final inode is 64-bit. */
    struct {
        oc_u64 device;
        oc_u32 pad0, old_inode, mode, links, uid, gid;
        oc_u64 rdevice;
        oc_u32 pad1;
        long long size;
        oc_u32 block_size;
        oc_u64 blocks;
        oc_u32 accessed, accessed_ns, modified, modified_ns, changed, changed_ns;
        oc_u64 inode;
    } s;
    _Static_assert(sizeof(s)==104,"ARM stat64 layout");
    long r=path?oc_syscall4(327,fd,(long)path,(long)&s,256):oc_syscall4(197,fd,(long)&s,0,0);
    if (r<0) return r;
    if (s.size<0) return -22;
    m->device=s.device; m->inode=s.inode; m->size=(oc_u64)s.size;
    m->mode=s.mode; m->uid=s.uid; m->gid=s.gid;
    m->modified=s.modified; m->modified_ns=s.modified_ns;
    m->changed=s.changed; m->changed_ns=s.changed_ns;
    return 0;
}
#endif

static long oc_stat(int fd, OcMeta *m) { return oc_metadata(fd,0,m); }

static long oc_beneath(int root, const char *path, unsigned options, unsigned mode) {
    char leaf[192];
    unsigned n, depth=0;
    int parent=root, owned=0;
    long fd=-22;
    if (!*path || *path=='/') return -22;
    for (;;) {
        n=0;
        while (*path && *path!='/') {
            char c=*path++;
            if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='_'||c=='-') || n+1>=sizeof leaf) goto done;
            leaf[n++]=c;
        }
        leaf[n]=0;
        if (!n || (n==1&&leaf[0]=='.') || (n==2&&leaf[0]=='.'&&leaf[1]=='.') || ++depth>16) goto done;
        if (!*path) { fd=oc_openat(parent,leaf,options,mode); break; }
        fd=oc_openat(parent,leaf,OC_DIRECTORY,0);
        if (fd<0) break;
        if (owned) (void)oc_close(parent);
        parent=(int)fd; owned=1; fd=-22;
        ++path;
    }
done:
    if (owned) (void)oc_close(parent);
    return fd;
}

static int oc_meta_equal(const OcMeta *a, const OcMeta *b) {
    return a->device==b->device && a->inode==b->inode && a->size==b->size &&
        a->mode==b->mode && a->uid==b->uid && a->gid==b->gid &&
        a->modified==b->modified && a->modified_ns==b->modified_ns &&
        a->changed==b->changed && a->changed_ns==b->changed_ns;
}
static inline int oc_meta_resealable(const OcMeta *a,const OcMeta *b) {
    return a->device==b->device&&a->size==b->size&&a->mode==b->mode&&a->uid==b->uid&&a->gid==b->gid;
}
static int oc_write_all(int fd, const void *input, unsigned n) {
    const char *p=input;
    while (n) {
        long r=oc_write(fd,p,n);
        if (r==-4) continue;
        if (r<=0) return 0;
        p+=r; n-=(unsigned)r;
    }
    return 1;
}
/* Read/copy once, checking both bytes and the opened inode's stable metadata.
 * Callers first walk parents and reject links/special leaves with oc_openat.
 */
static int oc_hash_copy(int input, int output, oc_u64 limit, char digest[65], OcMeta *metadata) {
    OcHash hash;
    OcMeta before,after;
    oc_u8 buffer[4096];
    oc_u64 total=0;
    if (oc_stat(input,&before)<0 || (before.mode&OC_TYPE)!=OC_REGULAR || before.size>limit) return 0;
    oc_hash_init(&hash);
    for (;;) {
        long n=oc_read(input,buffer,sizeof buffer);
        if (n==-4) continue;
        if (n<0) return 0;
        if (!n) break;
        total+=(unsigned)n;
        if (total>limit || total>before.size) return 0;
        oc_hash_add(&hash,buffer,(unsigned)n);
        if (output>=0 && !oc_write_all(output,buffer,(unsigned)n)) return OC_COPY_DEST;
    }
    if (total!=before.size || oc_stat(input,&after)<0 || !oc_meta_equal(&before,&after)) return 0;
    oc_hash_finish(&hash,digest);
    *metadata=before;
    return 1;
}
#endif
