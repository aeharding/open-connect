/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native freestanding ACC ignition observer.
 * ACC is a physical input: persist only a sustained OFF (>=3s) observed after
 * ON in this kernel; clear it if QuickStart resumes that same kernel.
 * Replaces ignition.sh + state.sh copy in /tmp/open-connect/ignition/.
 */
#include "core/oc-core.h"

#ifdef OC_HOST
#include <stdlib.h>
#endif

static int oc_ig_boot_id(int ram, long owner, long group, char out[37]) {
    OcMeta m;
    if (oc_metadata(ram,"boot-id",&m)<0 || (m.mode&OC_TYPE)!=0120000 ||
        m.size!=36 || m.uid!=(unsigned)owner || m.gid!=(unsigned)group) return 0;
    long n=oc_readlink(ram,"boot-id",out,36);
    if (n!=36) return 0;
    out[36]=0;
    return oc_uuid(out);
}

static int oc_ig_acc(int root) {
    char buf[8];
    if (oc_text(root,"sys/class/gpio/ACC_Sense/value",buf,sizeof buf,1)<0 || !oc_one_line(buf) || !buf[0] || buf[1]) return -1;
    return buf[0]=='1' ? 1 : (buf[0]=='0' ? 0 : -1);
}

static long oc_ig_open_lock(int ram, const char *name, unsigned opts, long owner, long group) {
    long fd=oc_openat(ram,name,opts,0600);
    OcMeta m;
    if (fd<0 || oc_stat((int)fd,&m)<0 || (m.mode&OC_TYPE)!=OC_REGULAR ||
        (m.mode&0077) || m.uid!=(unsigned)owner || m.gid!=(unsigned)group) {
        if (fd>=0) (void)oc_close((int)fd);
        return -1;
    }
    return fd;
}

static int oc_ignition_main(int argc, char **argv) {
    if (argc>2) return 1;
    const char *root_path=oc_root_path();
    long owner=oc_owner(), group=oc_group();
    unsigned sleep_ms=1000;
#ifdef OC_HOST
    const char *ms_env=getenv("OC_HOST_IGNITION_SLEEP_MS");
    if (ms_env && *ms_env) {
        oc_u64 v=0;
        if (oc_decimal(ms_env,&v) && v>=1 && v<=5000) sleep_ms=(unsigned)v;
    }
#endif
    int root=(int)oc_openat(OC_CWD,root_path,OC_DIRECTORY,0), ram=-1, rc=1;
    long ig_lock=-1;
    if (root<0) return 1;
    ram=oc_open_ram_dir(root);
    char boot[37];
    if (ram<0 || !oc_ig_boot_id(ram,owner,group,boot) || (argc==2 && !oc_equal(argv[1],boot))) goto out;

    /* One observer per kernel, independent of USB or listener readiness. */
    ig_lock=oc_ig_open_lock(ram,"ignition.lock",OC_RW|OC_CREATE,owner,group);
    if (ig_lock<0) goto out;
    long lr=oc_lock((int)ig_lock);
    if (lr<0) { rc=oc_is_wouldblock(lr)?0:1; goto out; }

    int seen_on=0, off_samples=0;
    rc=0;
    const char *recorded="-";
    for (;;) {
        OcMeta bm;
        if (oc_metadata(ram,"boot-id",&bm)<0 || (bm.mode&OC_TYPE)!=0120000) break;
        int acc=oc_ig_acc(root);
        if (acc<0) { rc=1; break; }
        const char *wanted=0;
        if (acc==1) {
            seen_on=1; off_samples=0; wanted="-";
        } else {
            if (!seen_on || (off_samples<3 && ++off_samples<3)) { oc_sleep_ms(sleep_ms); continue; }
            wanted=boot;
        }
        if (oc_equal(wanted,recorded)) { oc_sleep_ms(sleep_ms); continue; }

        long lfd=oc_ig_open_lock(ram,"lock",OC_RW,owner,group);
        if (lfd<0) { rc=1; break; }
        long tr=oc_lock((int)lfd);
        if (tr<0) {
            (void)oc_close((int)lfd);
            if (oc_is_wouldblock(tr)) { oc_sleep_ms(sleep_ms); continue; }
            rc=1; break;
        }

        char cur_boot[37], rec_buf[1024], *rec[13];
        int data=oc_open_data_dir(root);
        int ok=data>=0 && oc_ig_boot_id(ram,owner,group,cur_boot) && oc_equal(cur_boot,boot) &&
            oc_record_read_any(data,owner,group,rec_buf,sizeof rec_buf,rec) &&
            oc_equal(rec[1],"active") && oc_equal(rec[11],boot);
        if (ok && !oc_equal(rec[10],wanted)) {
            rec[10]=(char *)wanted;
            ok=oc_record_write_atomic(root,data,rec,0);
        }
        if (data>=0 && oc_close(data)<0) ok=0;
        if (oc_close((int)lfd)<0) ok=0;
        if (!ok) { rc=1; break; }
        recorded=wanted;
        oc_sleep_ms(sleep_ms);
    }
out:
    if (ig_lock>=0) (void)oc_close((int)ig_lock);
    if (ram>=0) (void)oc_close(ram);
    (void)oc_close(root);
    return rc;
}

#ifdef OC_HOST
int main(int argc, char **argv) { return oc_ignition_main(argc,argv); }
#else
int entry(int argc, char **argv) { return oc_ignition_main(argc,argv); }
__asm__(
    ".text\n"
    ".arm\n"
    ".global _start\n"
    ".type _start,%function\n"
    "_start:\n"
    "ldr r0,[sp]\n"
    "add r1,sp,#4\n"
    "bic sp,sp,#7\n"
    "bl entry\n"
    "mov r7,#1\n"
    "svc 0\n"
);
#endif
