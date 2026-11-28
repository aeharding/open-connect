/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Cold USB-only native installer binary.
 * Invoked by verified api under the global operation lock for `install`.
 */
#include "core/oc-core.h"

static int run(int argc, char **argv) {
    const char *root_path=oc_root_path();
    long owner=oc_owner(), group=oc_group();
    int root=(int)oc_openat(OC_CWD,root_path,OC_DIRECTORY,0);
    if (root<0) { (void)oc_write_all(1,"runtime_unavailable\n",20); return 1; }
    const char *err="install_failed";
    int ok=0;
    if (argc==4 && oc_equal(argv[1],"--boot-recover")) {
        ok=oc_boot_recover(root,root_path,argv[2],argv[3],owner,group);
        (void)oc_close(root);
        return ok?0:1;
    }
    if (argc==10 && oc_equal(argv[1],"--log-failure") && argv[2][0]=='/') {
        oc_diag_clear();
        if (!oc_equal(argv[5],"-"))
            oc_diag_set(argv[5],oc_equal(argv[6],"-")?0:argv[6],oc_equal(argv[7],"-")?0:argv[7],
                        oc_equal(argv[8],"-")?0:argv[8],oc_equal(argv[9],"-")?0:argv[9]);
        oc_usb_log_failure(root,argv[2],argv[3],argv[4]);
        (void)oc_close(root);
        return 0;
    }
#ifdef OC_HOST
    if (argc==3 && oc_equal(argv[1],"--test-compose")) {
        int data=oc_open_data_dir(root);
        ok=data>=0 && oc_compose_pkg(root,data,root_path,argv[2],&err);
        if (data>=0) (void)oc_close(data);
        (void)oc_close(root);
        if (!ok) { (void)oc_write_all(1,err,oc_length(err)); (void)oc_write_all(1,"\n",1); }
        return ok?0:1;
    }
#endif
    if (argc!=2 || argv[1][0]!='/') {
        (void)oc_close(root);
        (void)oc_write_all(1,"invalid_request\n",16);
        return 64;
    }
    ok=oc_install_run(root,root_path,argv[1],owner,group,&err);
    (void)oc_close(root);
    if (!ok) {
        (void)oc_write_all(1,err,oc_length(err));
        (void)oc_write_all(1,"\n",1);
        if (oc_diag.step[0]) {
            char dln[448];
            if (oc_join4(dln,sizeof dln,"DIAG|",oc_diag.step,"|",oc_diag.path[0]?oc_diag.path:"-") &&
                oc_join4(dln,sizeof dln,dln,"|",oc_diag.reason[0]?oc_diag.reason:"-","|") &&
                oc_join4(dln,sizeof dln,dln,oc_diag.expected[0]?oc_diag.expected:"-","|",oc_diag.actual[0]?oc_diag.actual:"-") &&
                oc_join(dln,sizeof dln,dln,"\n")) {
                (void)oc_write_all(1,dln,oc_length(dln));
            }
        }
        return 1;
    }
    return 0;
}

#ifdef OC_HOST
int main(int argc, char **argv) { return run(argc,argv); }
#else
int entry(unsigned *stack) { return run((int)stack[0],(char **)(stack+1)); }
__asm__(".text\n.arm\n.global _start\n.type _start,%function\n_start:\n"
        "mov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
