/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native selection's Linux 3.0 operations. Interface references, not imported
 * implementation: Linux v3.0 arch/arm/include/asm/unistd.h and
 * include/linux/dirent.h at https://github.com/torvalds/linux/tree/v3.0 .
 */
#ifndef OC_BOOT_SYSTEM_H
#define OC_BOOT_SYSTEM_H
#include "boot-plan.h"

#ifdef OC_HOST
#include <dirent.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
static long oc_parent(void) { return getppid(); }
/* Host fixtures exercise policy, without changing the host's CPU placement. */
static long oc_worker_cpu1(void) { return 0; }
static long oc_watch_parent(void) {
#ifdef __linux__
    return prctl(PR_SET_PDEATHSIG,SIGTERM)<0?-errno:0;
#else
    return 0;
#endif
}
static long oc_owner(void) { return getuid(); }
static long oc_group(void) { return getgid(); }
static long oc_lock(int fd) { return flock(fd,LOCK_EX|LOCK_NB)<0?-errno:0; }
static long oc_mkdir(int fd,const char *name,unsigned mode) { return mkdirat(fd,name,mode)<0?-errno:0; }
static long oc_unlink(int fd,const char *name) { return unlinkat(fd,name,0)<0?-errno:0; }
static long oc_rename(int fd,const char *from,const char *to) { return renameat(fd,from,fd,to)<0?-errno:0; }
static long oc_link(int from,const char *name,int to,const char *target) { return linkat(from,name,to,target,0)<0?-errno:0; }
static long oc_symlink(const char *source,int folder,const char *name) { return symlinkat(source,folder,name)<0?-errno:0; }
static long oc_mode(int fd,unsigned mode) { return fchmod(fd,mode)<0?-errno:0; }
static long oc_block(void) {
    sigset_t mask;
    sigemptyset(&mask); sigaddset(&mask,SIGHUP); sigaddset(&mask,SIGINT); sigaddset(&mask,SIGTERM); sigaddset(&mask,SIGPIPE);
    return sigprocmask(SIG_BLOCK,&mask,0)<0?-errno:0;
}
static void oc_cut(const char *phase) {
    const char *cut=getenv("OC_BOOT_CUT");
    if (cut && oc_equal(cut,phase)) _exit(97);
    const char *term=getenv("OC_BOOT_TERM");
    if (term && oc_equal(term,phase)) (void)raise(SIGTERM);
}
#else
static long oc_parent(void) { return oc_syscall4(64,0,0,0,0); }
static long oc_worker_cpu1(void) {
    unsigned mask=2;
    return oc_syscall4(241,0,sizeof mask,(long)&mask,0);
}
static long oc_watch_parent(void) { return oc_syscall4(172,1,15,0,0); }
static long oc_owner(void) { return oc_syscall4(199,0,0,0,0); }
static long oc_group(void) { return oc_syscall4(200,0,0,0,0); }
static long oc_lock(int fd) { return oc_syscall4(143,fd,6,0,0); }
static long oc_mkdir(int fd,const char *name,unsigned mode) { return oc_syscall4(323,fd,(long)name,mode,0); }
static long oc_unlink(int fd,const char *name) { return oc_syscall4(328,fd,(long)name,0,0); }
static long oc_rename(int fd,const char *from,const char *to) { return oc_syscall4(329,fd,(long)from,fd,(long)to); }
static long oc_link(int from,const char *name,int to,const char *target) {
    register long r0 __asm__("r0")=from;
    register long r1 __asm__("r1")=(long)name;
    register long r2 __asm__("r2")=to;
    register long r3 __asm__("r3")=(long)target;
    register long r4 __asm__("r4")=0;
    register long r7 __asm__("r7")=330;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r4),"r"(r7) : "memory","cc");
    return r0;
}
static long oc_symlink(const char *source,int folder,const char *name) {
    return oc_syscall4(331,(long)source,folder,(long)name,0);
}
static long oc_mode(int fd,unsigned mode) { return oc_syscall4(94,fd,mode,0,0); }
static long oc_block(void) {
    oc_u64 mask=20483; /* HUP, INT, TERM, PIPE. Keep blocked through exit. */
    return oc_syscall4(175,0,(long)&mask,0,8);
}
static void oc_cut(const char *phase) { (void)phase; }
#endif

static int oc_join(char *out,unsigned capacity,const char *a,const char *b) {
    unsigned n=oc_length(a),m=oc_length(b);
    if (n+m+1>capacity) return 0;
    for (unsigned i=0;i<n;++i) out[i]=a[i];
    for (unsigned i=0;i<=m;++i) out[n+i]=b[i];
    return 1;
}
static int oc_private(int fd) {
    OcMeta m;
    return oc_stat(fd,&m)>=0 && m.mode==(OC_DIR|0700) && m.uid==(unsigned)oc_owner() && m.gid==(unsigned)oc_group();
}
/* A bounded reader also supports procfs/sysfs files whose reported size is 0.
 * Immutable file readers separately verify regular type, metadata and digest.
 */
static int oc_text_fd(int fd,char *out,unsigned capacity) {
    unsigned total=0;
    while (total<capacity-1) {
        long n=oc_read(fd,out+total,capacity-1-total);
        if (n==-4) continue;
        if (n<0) return -1;
        if (!n) { out[total]=0; return (int)total; }
        for (long i=0;i<n;++i) if (!out[total+i]) return -1;
        total+=(unsigned)n;
    }
    char extra;
    if (oc_read(fd,&extra,1)!=0) return -1;
    out[total]=0;
    return (int)total;
}
static int oc_text(int root,const char *path,char *out,unsigned capacity,int virtual_file) {
    long fd=virtual_file?oc_openat(root,path,OC_READ,0):oc_beneath(root,path,OC_READ,0);
    if (fd<0) return -1;
    int n=oc_text_fd((int)fd,out,capacity);
    if (oc_close((int)fd)<0) n=-1;
    return n;
}
static int oc_verified_text(int folder,const char *name,const char *expected,char *out,unsigned capacity) {
    long fd=oc_beneath(folder,name,OC_READ,0);
    if (fd<0) return 0;
    OcMeta before,after;
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
static int oc_one_line(char *p) {
    unsigned n=oc_length(p);
    if (!n || p[n-1]!='\n') return 0;
    p[n-1]=0;
    for (unsigned i=0;i<n-1;++i) if ((unsigned char)p[i]<32 || (unsigned char)p[i]>=127) return 0;
    return 1;
}
static int oc_uuid(const char *p) {
    if (oc_length(p)!=36) return 0;
    for (unsigned i=0;i<36;++i) {
        if (i==8||i==13||i==18||i==23) { if (p[i]!='-') return 0; }
        else if (!((p[i]>='0'&&p[i]<='9')||(p[i]>='a'&&p[i]<='f'))) return 0;
    }
    return 1;
}
static int oc_random(int root,char out[33]) {
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
    for (unsigned i=0;i<sizeof bytes;++i) oc_put_hex(out+2*i,bytes[i],2);
    out[32]=0;
    return 1;
}

#endif
