/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Exercise the exact native data decoder; ordinary select tests cover debit. */
#include "boot-policy.h"
int main(int argc,char **argv) {
    if (argc!=4) return 64;
    OcBoot *b=&oc_boot;
    b->package=open(argv[1],O_RDONLY|O_DIRECTORY);
    if (b->package<0||!oc_load_manifest(b->package,argv[2],b->package_manifest,sizeof b->package_manifest,&b->pkg)||
        oc_text(b->package,"config",b->config,sizeof b->config,0)<0) return 2;
    return oc_config(b,b->config,b->flags,oc_equal(argv[3],"active"),0)?0:1;
}
