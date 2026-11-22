/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native settled-boot selector and maintenance-time plan sealer.
 * No shell or target libc is part of the native file-verification path.
 */
#include "boot-policy.h"

static int run(int argc, char **argv) {
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
    if (!sealing && !oc_equal(argv[1],"check")) return 64;
    long fd=oc_openat(OC_CWD,argv[2],OC_DIRECTORY,0);
    if (fd<0) return 1;
    long work=oc_beneath((int)fd,argv[3],OC_DIRECTORY,0);
    if (work<0) { (void)oc_close((int)fd); return 1; }
    int result=oc_plan_rows((int)fd,(int)work,0,1,sealing)?0:1;
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
