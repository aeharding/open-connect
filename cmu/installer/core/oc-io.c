/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Host/CMU syscall, descriptor, metadata, hashing copy, and directory iteration.
 * Target uses Linux 3.0 ARM EABI without target libc; OC_HOST exposes clean
 * environment-gated test hooks instead of source-patching.
 */
#include "oc-core.h"

#ifdef OC_HOST
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif

long oc_openat(int parent, const char *path, unsigned options, unsigned mode) {
    int flags=O_CLOEXEC|O_NOFOLLOW;
    if (!(options&OC_BLOCKING)) flags|=O_NONBLOCK;
    flags|=(options&OC_RW)?O_RDWR:((options&OC_WRITE)?O_WRONLY:O_RDONLY);
    if (options&OC_DIRECTORY) flags|=O_DIRECTORY;
    if (options&OC_CREATE) flags|=O_CREAT;
    if (options&OC_EXCLUSIVE) flags|=O_EXCL;
    if (options&OC_TRUNC) flags|=O_TRUNC;
    int fd=openat(parent,path,flags,mode);
    return fd<0?-errno:fd;
}
long oc_read(int fd, void *p, unsigned n) { long r=read(fd,p,n); return r<0?-errno:r; }
long oc_write(int fd, const void *p, unsigned n) { long r=write(fd,p,n); return r<0?-errno:r; }
long oc_seek_set(int fd, unsigned off) { off_t r=lseek(fd,(off_t)off,SEEK_SET); return r<0?-errno:(long)r; }
long oc_close(int fd) { return close(fd)<0?-errno:0; }
long oc_sync(int fd) { return fsync(fd)<0?-errno:0; }

static long oc_metadata_raw(int fd, const char *path, OcMeta *m) {
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
long oc_metadata(int fd, const char *path, OcMeta *m) {
    static int failed;
    const char *fault=getenv("OC_ALIAS_META_FAIL");
    if (path && fault && failed<2 && !strcmp(path,fault)) { ++failed; return -5; }
    long result=oc_metadata_raw(fd,path,m);
    if (result>=0 && path && !strcmp(path,"boot-id") && getenv("OC_BOOT_OWNER_FAIL")) ++m->uid;
    return result;
}
long oc_parent(void) { return getppid(); }
long oc_worker_cpu1(void) { return 0; }
long oc_watch_parent(void) {
#ifdef __linux__
    return prctl(PR_SET_PDEATHSIG,SIGTERM)<0?-errno:0;
#else
    return 0;
#endif
}
long oc_owner(void) { return getuid(); }
long oc_group(void) { return getgid(); }
long oc_lock(int fd) { return flock(fd,LOCK_EX|LOCK_NB)<0?-errno:0; }
long oc_lock_sh(int fd) { return flock(fd,LOCK_SH|LOCK_NB)<0?-errno:0; }
long oc_unlock(int fd) { return flock(fd,LOCK_UN)<0?-errno:0; }
int oc_lock_held_ex(int fd) {
    if (flock(fd,LOCK_SH|LOCK_NB)<0) return errno==EWOULDBLOCK || errno==EAGAIN;
    (void)flock(fd,LOCK_UN);
    return 0;
}
int oc_is_wouldblock(long err) { return err==-EWOULDBLOCK || err==-EAGAIN; }
void oc_sleep_ms(unsigned ms) {
    struct timespec ts;
    ts.tv_sec=(time_t)(ms/1000u);
    ts.tv_nsec=(long)(ms%1000u)*1000000L;
    (void)nanosleep(&ts,0);
}
long oc_fork(void) { pid_t p=fork(); return p<0?-errno:(long)p; }
long oc_waitpid(int pid, int *status) {
    for (;;) {
        pid_t r=waitpid(pid,status,0);
        if (r<0 && errno==EINTR) continue;
        return r<0?-errno:(long)r;
    }
}
long oc_pipe(int fds[2]) {
    if (pipe(fds)<0) return -errno;
    (void)fcntl(fds[0],F_SETFD,FD_CLOEXEC);
    (void)fcntl(fds[1],F_SETFD,FD_CLOEXEC);
    return 0;
}
long oc_dup2(int oldfd, int newfd) { return dup2(oldfd,newfd)<0?-errno:0; }
long oc_execve(const char *path, char *const argv[], char *const envp[]) {
    execve(path,argv,envp); return -errno;
}
void oc_exit(int code) { _exit(code); }
long oc_set_cloexec(int fd, int on) { return fcntl(fd,F_SETFD,on?FD_CLOEXEC:0)<0?-errno:0; }
const char *oc_root_path(void) {
    const char *r=getenv("OC_HOST_ROOT");
    return (r && *r=='/') ? r : "/";
}
int oc_nonroot_allowed(void) { return getenv("OC_HOST_NONROOT")!=0; }
long oc_mkdir(int fd, const char *name, unsigned mode) { return mkdirat(fd,name,mode)<0?-errno:0; }
long oc_unlink(int fd, const char *name) { return unlinkat(fd,name,0)<0?-errno:0; }
long oc_rmdirat(int fd, const char *name) { return unlinkat(fd,name,AT_REMOVEDIR)<0?-errno:0; }
long oc_rename(int fd, const char *from, const char *to) { return renameat(fd,from,fd,to)<0?-errno:0; }
long oc_link(int from, const char *name, int to, const char *target) {
    const char *foreign=getenv("OC_ALIAS_FOREIGN");
    const char *fault=getenv("OC_ALIAS_LINK_FAIL");
    const char *after=getenv("OC_ALIAS_LINK_AFTER");
    if (foreign && !strcmp(target,foreign)) {
        long fd=oc_openat(to,target,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        if (fd>=0) { (void)oc_write_all((int)fd,"foreign\n",8); (void)oc_close((int)fd); }
        return -17;
    }
    if (fault && !strcmp(target,fault)) return -5;
    if (linkat(from,name,to,target,0)<0) return -errno;
    return after && !strcmp(target,after) ? -5 : 0;
}
long oc_symlink(const char *source, int folder, const char *name) { return symlinkat(source,folder,name)<0?-errno:0; }
long oc_readlink(int folder, const char *name, char *out, unsigned capacity) {
    long n=readlinkat(folder,name,out,capacity); return n<0?-errno:n;
}
long oc_mode(int fd, unsigned mode) { return fchmod(fd,mode)<0?-errno:0; }
long oc_fchown(int fd, unsigned uid, unsigned gid) { return fchown(fd,(uid_t)uid,(gid_t)gid)<0?-errno:0; }
long oc_block(void) {
    sigset_t mask;
    sigemptyset(&mask); sigaddset(&mask,SIGHUP); sigaddset(&mask,SIGINT); sigaddset(&mask,SIGTERM); sigaddset(&mask,SIGPIPE);
    return sigprocmask(SIG_BLOCK,&mask,0)<0?-errno:0;
}
void oc_cut(const char *phase) {
    const char *cut=getenv("OC_BOOT_CUT");
    if (cut && oc_equal(cut,phase)) _exit(97);
    const char *term=getenv("OC_BOOT_TERM");
    if (term && oc_equal(term,phase)) (void)raise(SIGTERM);
}
int oc_stock_meta(int root, OcMeta *stock) {
    const char *override=getenv("OC_HOST_STOCK_ROOT");
    int ok;
    if (override && *override) {
        long fd=oc_openat(OC_CWD,override,OC_DIRECTORY,0);
        if (fd<0) return 0;
        ok=oc_stat((int)fd,stock)>=0;
        if (oc_close((int)fd)<0) ok=0;
    } else {
        ok=oc_stat(root,stock)>=0;
    }
    if (ok && getenv("OC_TOUCH_WRONG_FS")) ++stock->device;
    return ok;
}
const char *oc_pin_digest(const char *key, const char *prod) {
    static char table[4096];
    static int loaded;
    if (!loaded) {
        loaded=1;
        const char *path=getenv("OC_HOST_PINS");
        if (path && *path) {
            int fd=open(path,O_RDONLY);
            if (fd>=0) {
                long n=read(fd,table,sizeof table-1);
                if (n>0) table[n]=0;
                close(fd);
            }
        }
    }
    if (!table[0]) return prod;
    const char *p=table;
    unsigned klen=oc_length(key);
    while (*p) {
        const char *line=p;
        while (*p && *p!='\n') ++p;
        const char *end=p;
        if (*p=='\n') ++p;
        if ((unsigned)(end-line)==klen+65 && line[klen]=='=' && !memcmp(line,key,klen)) {
            static char hits[16][65];
            static unsigned slot;
            char *dst=hits[slot++ & 15];
            memcpy(dst,line+klen+1,64);
            dst[64]=0;
            return dst;
        }
    }
    return prod;
}
int oc_dir_iter(int folder, int (*cb)(const char *name, void *ctx), void *ctx) {
    int copy=dup(folder);
    if (copy<0) return 0;
    DIR *directory=fdopendir(copy);
    if (!directory) { close(copy); return 0; }
    rewinddir(directory);
    struct dirent *entry;
    int ok=1;
    for (;;) {
        errno=0;
        entry=readdir(directory);
        if (!entry) { if (errno) ok=0; break; }
        const char *name=entry->d_name;
        if (oc_equal(name,".")||oc_equal(name,"..")) continue;
        int r=cb(name,ctx);
        if (r<0) { ok=0; break; }
        if (r==0) break;
    }
    if (closedir(directory)<0) ok=0;
    return ok;
}
#else
#if !defined(__arm__) || !defined(__ARM_EABI__)
#error "Target requires 32-bit ARM EABI"
#endif
void *memcpy(void *dst, const void *src, unsigned n) {
    unsigned char *d=(unsigned char *)dst;
    const unsigned char *s=(const unsigned char *)src;
    while (n--) *d++=*s++;
    return dst;
}
void *memset(void *dst, int c, unsigned n) {
    unsigned char *d=(unsigned char *)dst;
    while (n--) *d++=(unsigned char)c;
    return dst;
}
static long oc_syscall4(long number, long a, long b, long c, long d) {
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    register long r3 __asm__("r3")=d;
    register long r7 __asm__("r7")=number;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r7) : "memory","cc");
    return r0;
}
long oc_openat(int parent, const char *path, unsigned options, unsigned mode) {
    unsigned flags=0400000|02000000|0100000; /* ARM LARGEFILE|CLOEXEC|NOFOLLOW */
    if (!(options&OC_BLOCKING)) flags|=04000; /* O_NONBLOCK */
    flags|=(options&OC_RW)?2:((options&OC_WRITE)?1:0);
    if (options&OC_DIRECTORY) flags|=040000;
    if (options&OC_CREATE) flags|=0100;
    if (options&OC_EXCLUSIVE) flags|=0200;
    if (options&OC_TRUNC) flags|=01000;
    return oc_syscall4(322,parent,(long)path,flags,mode);
}
long oc_read(int fd, void *p, unsigned n) { return oc_syscall4(3,fd,(long)p,n,0); }
long oc_write(int fd, const void *p, unsigned n) { return oc_syscall4(4,fd,(long)p,n,0); }
long oc_seek_set(int fd, unsigned off) { return oc_syscall4(19,fd,(long)off,0,0); }
long oc_close(int fd) { return oc_syscall4(6,fd,0,0,0); }
long oc_sync(int fd) { return oc_syscall4(118,fd,0,0,0); }
long oc_metadata(int fd, const char *path, OcMeta *m) {
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
long oc_parent(void) { return oc_syscall4(64,0,0,0,0); }
long oc_worker_cpu1(void) {
    unsigned mask=2;
    return oc_syscall4(241,0,sizeof mask,(long)&mask,0);
}
long oc_watch_parent(void) { return oc_syscall4(172,1,15,0,0); }
long oc_owner(void) { return oc_syscall4(199,0,0,0,0); }
long oc_group(void) { return oc_syscall4(200,0,0,0,0); }
long oc_lock(int fd) { return oc_syscall4(143,fd,6,0,0); }
long oc_lock_sh(int fd) { return oc_syscall4(143,fd,5,0,0); }
long oc_unlock(int fd) { return oc_syscall4(143,fd,8,0,0); }
int oc_lock_held_ex(int fd) {
    long r=oc_syscall4(143,fd,5,0,0); /* LOCK_SH|LOCK_NB */
    if (r==-11) return 1; /* EAGAIN/EWOULDBLOCK: exclusive lock is held */
    if (r>=0) (void)oc_syscall4(143,fd,8,0,0); /* LOCK_UN */
    return 0;
}
int oc_is_wouldblock(long err) { return err==-11; }
void oc_sleep_ms(unsigned ms) {
    unsigned sec=0;
    while (ms>=1000u) { __asm__ volatile("" : "+r"(ms)); ms-=1000u; ++sec; }
    struct { long sec, nsec; } ts={(long)sec,(long)ms*1000000L};
    (void)oc_syscall4(162,(long)&ts,0,0,0);
}
long oc_fork(void) { return oc_syscall4(2,0,0,0,0); }
long oc_waitpid(int pid, int *status) {
    for (;;) {
        long r=oc_syscall4(114,pid,(long)status,0,0);
        if (r==-4) continue;
        return r;
    }
}
long oc_pipe(int fds[2]) {
    long r=oc_syscall4(42,(long)fds,0,0,0);
    if (r>=0) { (void)oc_syscall4(55,fds[0],2,1,0); (void)oc_syscall4(55,fds[1],2,1,0); }
    return r;
}
long oc_dup2(int oldfd, int newfd) { return oc_syscall4(63,oldfd,newfd,0,0); }
long oc_execve(const char *path, char *const argv[], char *const envp[]) {
    return oc_syscall4(11,(long)path,(long)argv,(long)envp,0);
}
void oc_exit(int code) { (void)oc_syscall4(1,code,0,0,0); for(;;){} }
long oc_set_cloexec(int fd, int on) { return oc_syscall4(55,fd,2,on?1:0,0); }
const char *oc_root_path(void) { return "/"; }
int oc_nonroot_allowed(void) { return 0; }
long oc_mkdir(int fd, const char *name, unsigned mode) { return oc_syscall4(323,fd,(long)name,mode,0); }
long oc_unlink(int fd, const char *name) { return oc_syscall4(328,fd,(long)name,0,0); }
long oc_rmdirat(int fd, const char *name) { return oc_syscall4(328,fd,(long)name,0x200,0); }
long oc_rename(int fd, const char *from, const char *to) { return oc_syscall4(329,fd,(long)from,fd,(long)to); }
long oc_link(int from, const char *name, int to, const char *target) {
    register long r0 __asm__("r0")=from;
    register long r1 __asm__("r1")=(long)name;
    register long r2 __asm__("r2")=to;
    register long r3 __asm__("r3")=(long)target;
    register long r4 __asm__("r4")=0;
    register long r7 __asm__("r7")=330;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7) : "memory","cc");
    return r0;
}
long oc_symlink(const char *source, int folder, const char *name) { return oc_syscall4(331,(long)source,folder,(long)name,0); }
long oc_readlink(int folder, const char *name, char *out, unsigned capacity) {
    return oc_syscall4(332,folder,(long)name,(long)out,capacity);
}
long oc_mode(int fd, unsigned mode) { return oc_syscall4(94,fd,mode,0,0); }
long oc_fchown(int fd, unsigned uid, unsigned gid) { return oc_syscall4(207,fd,uid,gid,0); }
long oc_block(void) {
    oc_u64 mask=20483; /* HUP, INT, TERM, PIPE. */
    return oc_syscall4(175,0,(long)&mask,0,8);
}
int oc_stock_meta(int root, OcMeta *stock) { return oc_stat(root,stock)>=0; }
#ifdef OC_TEST_PINFILE
const char *oc_pin_digest(const char *key, const char *prod) {
    static char table[8192];
    static int loaded;
    if (!loaded) {
        loaded=1;
        long fd=oc_openat(OC_CWD,"/etc/oc-test-pins",OC_READ,0);
        if (fd>=0) {
            unsigned used=0;
            while (used+1<sizeof table) {
                long n=oc_read((int)fd,table+used,sizeof table-1-used);
                if (n==-4) continue;
                if (n<=0) break;
                used+=(unsigned)n;
            }
            table[used]=0;
            (void)oc_close((int)fd);
        }
    }
    if (!table[0]) return prod;
    const char *p=table;
    unsigned klen=oc_length(key);
    while (*p) {
        const char *line=p;
        while (*p && *p!='\n') ++p;
        const char *end=p;
        if (*p=='\n') ++p;
        if ((unsigned)(end-line)==klen+65 && line[klen]=='=' && oc_prefix(line,key)) {
            static char hits[16][65];
            static unsigned slot;
            char *dst=hits[slot++ & 15];
            memcpy(dst,line+klen+1,64);
            dst[64]=0;
            return dst;
        }
    }
    return prod;
}
#else
const char *oc_pin_digest(const char *key, const char *prod) { (void)key; return prod; }
#endif
int oc_dir_iter(int folder, int (*cb)(const char *name, void *ctx), void *ctx) {
    unsigned char buffer[4096];
    if (oc_syscall4(19,folder,0,0,0)<0) return 0;
    for (;;) {
        long n=oc_syscall4(217,folder,(long)buffer,sizeof buffer,0);
        if (n==-4) continue;
        if (n<0) return 0;
        if (!n) break;
        unsigned at=0;
        while (at<(unsigned)n) {
            if ((unsigned)n-at<20) return 0;
            unsigned length=buffer[at+16]+((unsigned)buffer[at+17]<<8);
            if (length<20 || length>(unsigned)n-at) return 0;
            char *name=(char *)buffer+at+19;
            unsigned size=length-19, j=0;
            while (j<size && name[j]) ++j;
            if (j==size) return 0;
            if (!oc_equal(name,".") && !oc_equal(name,"..")) {
                int r=cb(name,ctx);
                if (r<0) return 0;
                if (r==0) return 1;
            }
            at+=length;
        }
    }
    return 1;
}
#endif

long oc_beneath(int root, const char *path, unsigned options, unsigned mode) {
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

int oc_meta_equal(const OcMeta *a, const OcMeta *b) {
    return a->device==b->device && a->inode==b->inode && a->size==b->size &&
        a->mode==b->mode && a->uid==b->uid && a->gid==b->gid &&
        a->modified==b->modified && a->modified_ns==b->modified_ns &&
        a->changed==b->changed && a->changed_ns==b->changed_ns;
}

int oc_meta_resealable(const OcMeta *a, const OcMeta *b) {
    return a->device==b->device && a->size==b->size && a->mode==b->mode && a->uid==b->uid && a->gid==b->gid;
}

int oc_write_all(int fd, const void *input, unsigned n) {
    const char *p=input;
    while (n) {
        long r=oc_write(fd,p,n);
        if (r==-4) continue;
        if (r<=0) return 0;
        p+=r; n-=(unsigned)r;
    }
    return 1;
}

int oc_hash_copy(int input, int output, oc_u64 limit, char digest[65], OcMeta *metadata) {
    OcHash hash;
    OcMeta before, after;
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

int oc_private(int fd) {
    OcMeta m;
    return oc_stat(fd,&m)>=0 && m.mode==(OC_DIR|0700) && m.uid==(unsigned)oc_owner() && m.gid==(unsigned)oc_group();
}

int oc_open_private(int parent, const char *path) {
    long fd=oc_beneath(parent,path,OC_DIRECTORY,0);
    if (fd<0) return -1;
    if (!oc_private((int)fd)) { (void)oc_close((int)fd); return -1; }
    return (int)fd;
}

int oc_absent_at(int root, const char *path) {
    char parent[192];
    unsigned slash=0, n=oc_length(path);
    for (unsigned i=0; i<n; ++i) if (path[i]=='/') slash=i;
    long directory=root;
    if (slash) {
        if (slash>=sizeof parent) return 0;
        for (unsigned i=0; i<slash; ++i) parent[i]=path[i];
        parent[slash]=0;
        directory=oc_beneath(root,parent,OC_DIRECTORY,0);
        if (directory<0) return 0;
        path+=slash+1;
    }
    long fd=oc_openat((int)directory,path,OC_READ,0);
    if (fd>=0) (void)oc_close((int)fd);
    if (slash) (void)oc_close((int)directory);
    return fd==-2;
}

int oc_text_fd(int fd, char *out, unsigned capacity) {
    unsigned total=0;
    while (total<capacity-1) {
        long n=oc_read(fd,out+total,capacity-1-total);
        if (n==-4) continue;
        if (n<0) return -1;
        if (!n) { out[total]=0; return (int)total; }
        for (long i=0; i<n; ++i) if (!out[total+i]) return -1;
        total+=(unsigned)n;
    }
    char extra;
    if (oc_read(fd,&extra,1)!=0) return -1;
    out[total]=0;
    return (int)total;
}

int oc_text(int root, const char *path, char *out, unsigned capacity, int virtual_file) {
    long fd=virtual_file?oc_openat(root,path,OC_READ,0):oc_beneath(root,path,OC_READ,0);
    if (fd<0) return -1;
    int n=oc_text_fd((int)fd,out,capacity);
    if (oc_close((int)fd)<0) n=-1;
    return n;
}

int oc_verified_text(int folder, const char *name, const char *expected, char *out, unsigned capacity) {
    long fd=oc_beneath(folder,name,OC_READ,0);
    if (fd<0) return 0;
    OcMeta before, after;
    int n=-1;
    if (oc_stat((int)fd,&before)>=0 && (before.mode&OC_TYPE)==OC_REGULAR && before.size<capacity)
        n=oc_text_fd((int)fd,out,capacity);
    int ok=n>=0 && (oc_u64)n==before.size && oc_stat((int)fd,&after)>=0 && oc_meta_equal(&before,&after);
    if (oc_close((int)fd)<0) ok=0;
    if (ok) {
        OcHash hash; char digest[65];
        oc_hash_init(&hash); oc_hash_add(&hash,out,(unsigned)n); oc_hash_finish(&hash,digest);
        ok=oc_equal(digest,expected);
    }
    return ok;
}

int oc_new_text(int folder, const char *name, const char *text, unsigned mode) {
    long fd=oc_openat(folder,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,mode);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,text,oc_length(text)) && oc_mode((int)fd,mode)>=0;
    if (oc_close((int)fd)<0) ok=0;
    return ok;
}

int oc_random(int root, char out[33]) {
    unsigned char bytes[16]; unsigned used=0;
    long fd=oc_openat(root,"dev/urandom",OC_READ,0);
    if (fd<0) return 0;
    while (used<sizeof bytes) {
        long n=oc_read((int)fd,bytes+used,sizeof bytes-used);
        if (n==-4) continue;
        if (n<=0) { (void)oc_close((int)fd); return 0; }
        used+=(unsigned)n;
    }
    if (oc_close((int)fd)<0) return 0;
    for (unsigned i=0; i<sizeof bytes; ++i) oc_put_hex(out+2*i,bytes[i],2);
    out[32]=0;
    return 1;
}

int oc_join4(char *out, unsigned cap, const char *a, const char *b, const char *c, const char *d) {
    const char *parts[4]={a,b,c,d};
    unsigned at=0;
    for (unsigned i=0; i<4; ++i) {
        if (!parts[i]) continue;
        unsigned n=oc_length(parts[i]);
        if (at+n>=cap) return 0;
        for (unsigned j=0; j<n; ++j) out[at++]=parts[i][j];
    }
    if (!cap) return 0;
    out[at]=0;
    return 1;
}

void oc_u64_dec(oc_u64 v, char out[24]) {
    static const oc_u64 p10[20]={
        10000000000000000000ULL,1000000000000000000ULL,100000000000000000ULL,
        10000000000000000ULL,1000000000000000ULL,100000000000000ULL,
        10000000000000ULL,1000000000000ULL,100000000000ULL,10000000000ULL,
        1000000000ULL,100000000ULL,10000000ULL,1000000ULL,100000ULL,
        10000ULL,1000ULL,100ULL,10ULL,1ULL
    };
    unsigned n=0;
    for (unsigned i=0; i<20; ++i) {
        unsigned d=0;
        while (v>=p10[i]) {
#ifndef OC_HOST
            __asm__ volatile("" : "+r"(d));
#endif
            v-=p10[i]; ++d;
        }
        if (d || n || i==19) out[n++]=(char)('0'+d);
    }
    out[n]=0;
}

int oc_meta_mode_str(const OcMeta *m, char out[40]) {
    unsigned perm=m->mode&07777, at=0, started=0;
    for (int sh=9; sh>=0; sh-=3) {
        unsigned d=(perm>>sh)&7u;
        if (d || started || sh==0) { out[at++]=(char)('0'+d); started=1; }
    }
    out[at++]=':';
    char uid_s[24], gid_s[24];
    oc_u64_dec(m->uid,uid_s); oc_u64_dec(m->gid,gid_s);
    out[at]=0;
    return oc_join4(out+at,40-at,uid_s,":",gid_s,0);
}

int oc_hash_file_at(int dir, const char *name, char digest[65], OcMeta *meta) {
    long fd=oc_openat(dir,name,OC_READ,0);
    if (fd<0) return 0;
    OcMeta tmp={0};
    int ok=oc_hash_copy((int)fd,-1,33554432,digest,meta?meta:&tmp)==OC_COPY_OK;
    if (oc_close((int)fd)<0) ok=0;
    return ok;
}

int oc_copy_file_at(int src_dir, const char *src_name, int dst_dir, const char *dst_name,
                    unsigned mode, int excl, int do_sync, char digest_out[65]) {
    long sfd=oc_openat(src_dir,src_name,OC_READ,0);
    if (sfd<0) return 0;
    unsigned fl=OC_WRITE|OC_CREATE|(excl?OC_EXCLUSIVE:OC_TRUNC);
    long dfd=oc_openat(dst_dir,dst_name,fl,mode);
    if (dfd<0) { (void)oc_close((int)sfd); return 0; }
    char dig[65]; OcMeta sm={0};
    int ok=oc_hash_copy((int)sfd,(int)dfd,33554432,digest_out?digest_out:dig,&sm)==OC_COPY_OK &&
        oc_mode((int)dfd,mode)>=0 && (!do_sync || oc_sync((int)dfd)>=0);
    if (oc_close((int)sfd)<0) ok=0;
    if (oc_close((int)dfd)<0) ok=0;
    return ok;
}

#ifdef OC_HOST
extern char **environ;
#endif
int oc_run_cmd_io(const char *path, char *const argv[], int in_fd, int out_fd,
                  char *cap_buf, unsigned cap_sz, int keep_fd) {
    int pfd[2]={-1,-1};
    if (cap_buf && oc_pipe(pfd)<0) return -1;
    long pid=oc_fork();
    if (pid<0) {
        if (pfd[0]>=0) { (void)oc_close(pfd[0]); (void)oc_close(pfd[1]); }
        return -1;
    }
    if (pid==0) {
        if (keep_fd>=0) (void)oc_set_cloexec(keep_fd,0);
        long devnull=oc_openat(OC_CWD,"/dev/null",OC_RW,0);
        if (devnull>=0) {
            if (in_fd<0) (void)oc_dup2((int)devnull,0);
            (void)oc_dup2((int)devnull,2);
            if (!cap_buf && out_fd<0) (void)oc_dup2((int)devnull,1);
            if (devnull>2) (void)oc_close((int)devnull);
        }
        if (in_fd>=0) { (void)oc_dup2(in_fd,0); if (in_fd>2) (void)oc_close(in_fd); }
        if (cap_buf) { (void)oc_dup2(pfd[1],1); (void)oc_close(pfd[0]); (void)oc_close(pfd[1]); }
        else if (out_fd>=0) { (void)oc_dup2(out_fd,1); if (out_fd>2) (void)oc_close(out_fd); }
#ifdef OC_HOST
        (void)oc_execve(path,argv,environ);
#else
        char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin","LC_ALL=C",0};
        (void)oc_execve(path,argv,env);
#endif
        oc_exit(127);
    }
    if (cap_buf) {
        (void)oc_close(pfd[1]);
        unsigned at=0; char drain[64];
        for (;;) {
            int full=at+1>=cap_sz;
            long r=oc_read(pfd[0],full?drain:(cap_buf+at),full?(unsigned)sizeof drain:(cap_sz-1-at));
            if (r==-4) continue;
            if (r<=0) break;
            if (!full) at+=(unsigned)r;
        }
        cap_buf[at]=0;
        (void)oc_close(pfd[0]);
    }
    int st=0;
    if (oc_waitpid((int)pid,&st)<0) return -1;
    return (st&0x7f) ? (128+(st&0x7f)) : ((st>>8)&0xff);
}
#ifdef OC_HOST
static int oc_open_host_dir(const char *env_name, int root, const char *rel) {
    const char *p=getenv(env_name);
    if (p && *p) {
        long fd=oc_openat(OC_CWD,p,OC_DIRECTORY,0);
        if (fd<0) return -1;
        if (!oc_private((int)fd)) { (void)oc_close((int)fd); return -1; }
        return (int)fd;
    }
    return oc_open_private(root,rel);
}
int oc_open_data_dir(int root) { return oc_open_host_dir("OC_HOST_DATA",root,OC_DATA); }
int oc_open_ram_dir(int root) { return oc_open_host_dir("OC_HOST_RAM",root,OC_RAM); }
int oc_data_absent(int root) {
    const char *p=getenv("OC_HOST_DATA");
    if (p && *p) { OcMeta m; return oc_metadata(OC_CWD,p,&m)==-ENOENT; }
    return oc_absent_at(root,OC_DATA);
}
int oc_data_base(const char *root_path, char *out, unsigned cap) {
    const char *p=getenv("OC_HOST_DATA");
    if (p && *p) return oc_join(out,cap,"",p);
    return oc_join(out,cap,oc_equal(root_path,"/")?"":root_path,"/" OC_DATA);
}
#endif
