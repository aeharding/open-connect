/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native settled-boot selector and maintenance-time plan sealer.
 * No shell or target libc is part of the native file-verification path.
 */
#include "boot-policy.h"

static int run(int argc, char **argv) {
    if (argc==5&&oc_equal(argv[1],"copy-ui")&&argv[2][0]=='/'&&oc_hex(argv[3],64)&&
        oc_prefix(argv[4],".feature-")&&oc_key(argv[4])) {
        /* The verified shell owns fd9's operation lock. No debit, NVRAM,
         * publication, aliases or side effects outside its private stage.
         */
        for (const char *p=argv[4];*p;++p) if (*p=='/') return 64;
        OcBoot *b=&oc_boot;
        b->owner=oc_owner();b->group=oc_group();
        b->root=(int)oc_openat(OC_CWD,argv[2],OC_DIRECTORY,0);
        if (b->root<0) return 1;
        b->data=oc_open_private(b->root,OC_DATA);b->ram=oc_open_private(b->root,OC_RAM);
        if (b->data<0||b->ram<0||!oc_record(b)||!oc_equal(b->record_fields[5],argv[3])||
            !oc_mounts(b)||!oc_policy_load(b)||!oc_load(b)||b->metadata_drift||
            !oc_absent_at(b->ram,"selected")||!oc_absent_at(b->ram,"feature")) return 1;
        b->stage=oc_open_private(b->ram,argv[4]);
        return b->stage>=0&&oc_ui_stage(b)?0:1;
    }
#ifdef OC_HOST
    if (argc==3 && (oc_equal(argv[1],"select")||oc_equal(argv[1],"select-gated"))) {
        long root=oc_openat(OC_CWD,argv[2],OC_DIRECTORY,0);
#else
    if (argc==2 && (oc_equal(argv[1],"select")||oc_equal(argv[1],"select-gated"))) {
        long root=oc_openat(OC_CWD,"/",OC_DIRECTORY,0);
#endif
        if (root<0) return OC_REFUSE;
        int result=oc_selection((int)root,oc_equal(argv[1],"select-gated"));
        (void)oc_close((int)root);
        return result;
    }
    if (argc!=4 || argv[2][0]!='/') return 64;
    int sealing=oc_equal(argv[1],"seal");
    int mode=sealing?1:oc_equal(argv[1],"recheck")?2:oc_equal(argv[1],"verify")?3:0;
    if (!mode && !oc_equal(argv[1],"check")) return 64;
    long fd=oc_openat(OC_CWD,argv[2],OC_DIRECTORY,0);
    if (fd<0) return 1;
    long work=oc_beneath((int)fd,argv[3],OC_DIRECTORY,0);
    if (work<0) { (void)oc_close((int)fd); return 1; }
    int result=oc_plan_rows((int)fd,(int)work,0,1,mode)?0:1;
    if (sealing && oc_sync(1)<0) result=1;
    if (oc_close((int)work)<0 || oc_close((int)fd)<0) result=1;
    if (result) (void)oc_write_all(2,"boot_plan_refused\n",18);
    return result;
}
#ifdef OC_HOST
int main(int argc, char **argv) { return run(argc,argv); }
#else
int entry(unsigned *stack) { return run((int)stack[0],(char **)(stack+1)); }
__asm__(".text\n.global _start\n.type _start,%function\n"
        "_start:\nmov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
