/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Test the production streaming hash and descriptor traversal with real files.
 */
#include "boot-io.h"
#ifdef OC_HOST
#include <stdio.h>
int main(int argc, char **argv) {
    char digest[65];
    OcMeta m;
    long root,input,output=-1;
    if (argc!=4 && argc!=5) return 64;
    root=oc_openat(OC_CWD,argv[1],OC_DIRECTORY,0);
    if (root<0) return 1;
    input=oc_beneath((int)root,argv[2],OC_READ,0);
    if (input<0) { (void)oc_close((int)root); return 2; }
    if (argc==5) {
        output=oc_beneath((int)root,argv[4],OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        if (output<0) { (void)oc_close((int)input); (void)oc_close((int)root); return 3; }
    }
    unsigned limit=0;
    for (const char *p=argv[3]; *p; ++p) {
        if (*p<'0'||*p>'9'||limit>10000000) return 64;
        limit=limit*10+(unsigned)(*p-'0');
    }
    int ok=oc_hash_copy((int)input,(int)output,limit,digest,&m);
    if (output>=0) { if (oc_sync((int)output)<0) ok=0; if (oc_close((int)output)<0) ok=0; }
    if (oc_close((int)input)<0 || oc_close((int)root)<0) ok=0;
    if (!ok) return 4;
    printf("%s\n%llu %llu %llu %u %u %u %llu %u %llu %u\n",digest,
           m.device,m.inode,m.size,m.mode,m.uid,m.gid,m.modified,m.modified_ns,m.changed,m.changed_ns);
    return 0;
}
#else
/* Compile the real ARM wrappers and layout without a target sysroot/libc. */
int entry(unsigned *stack) {
    OcMeta m;
    char digest[65];
    long root=oc_openat(OC_CWD,"/",OC_DIRECTORY,0);
    if (root<0) return 1;
    long input=oc_beneath((int)root,"proc/version",OC_READ,0);
    int result=input<0 || !oc_hash_copy((int)input,-1,4096,digest,&m);
    if (input>=0) (void)oc_close((int)input);
    (void)oc_sync((int)root); (void)oc_close((int)root);
    return result+(stack[0]==0);
}
__asm__(".text\n.global _start\n.type _start,%function\n"
        "_start:\nmov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
