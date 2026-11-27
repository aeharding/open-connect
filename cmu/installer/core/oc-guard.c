/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Shared exact-v74 firmware identity and physical mount guards.
 * Linked into both boot-select and api so mount and OEM attestation rules
 * have a single authoritative implementation.
 */
#include "oc-core.h"
#ifdef OC_HOST
#include <stdlib.h>
#endif

static int oc_mounts_scan(int root, char *scratch, unsigned cap, int allow_rw, int persist_only) {
    if (oc_text(root,"proc/self/mounts",scratch,cap,1)<0) return 0;
    unsigned rcount=0, data=0, rootfs=0;
    char *p=scratch;
    while (*p) {
        char *f[6]; unsigned n=0;
        while (*p && *p!='\n') {
            if (*p==' '||*p=='\t') { ++p; continue; }
            if (n==6) return 0;
            f[n++]=p;
            while (*p && *p!=' ' && *p!='\t' && *p!='\n') ++p;
            if (*p==' '||*p=='\t') *p++=0;
        }
        if (!*p || n!=6) return 0;
        *p++=0;
        if (!persist_only && oc_equal(f[1],"/")) {
            if (oc_equal(f[0],"rootfs")&&oc_equal(f[2],"rootfs")&&oc_equal(f[3],"rw")&&!rcount&&!rootfs) ++rootfs;
            else {
                if (!oc_equal(f[0],"/dev/ffx01p1")||!oc_equal(f[2],"relfs")||
                    (!oc_equal(f[3],"ro,noatime")&&!(allow_rw&&oc_equal(f[3],"rw,noatime")))) return 0;
                ++rcount;
            }
        }
        if (oc_equal(f[1],"/tmp/mnt/data_persist")) {
            if (!oc_equal(f[0],"/dev/mmcblk0p2")||!oc_equal(f[2],"relfs")) {
                if (persist_only) continue;
                return 0;
            }
            char options[256];
            if (!oc_join(options,sizeof options,",",f[3])||!oc_join(options,sizeof options,options,",")) return 0;
            int rw=0;
            for (char *q=options; *q; ++q) if (oc_prefix(q,",rw,")) ++rw;
            if (rw!=1) { if (persist_only) continue; return 0; }
            ++data;
        }
        if (!persist_only &&
            (oc_equal(f[1],"/" OC_DATA)||oc_prefix(f[1],"/" OC_DATA "/")||
             oc_equal(f[1],"/" OC_RAM)||oc_prefix(f[1],"/" OC_RAM "/"))) return 0;
    }
    return persist_only ? (data==1) : (rcount==1 && data==1);
}

int oc_mounts_mode(int root, char *scratch, unsigned cap, int allow_rw) {
    return oc_mounts_scan(root,scratch,cap,allow_rw,0);
}

int oc_version_ok(int root, char *scratch, unsigned cap) {
    int n=oc_text(root,"jci/version.ini",scratch,cap,0);
    if (n<=0) return 0;
    unsigned v=0, pa=0, fl=0;
    char *p=scratch;
    while (*p) {
        char *line=p;
        while (*p && *p!='\n') ++p;
        if (*p=='\n') *p++=0;
        if (oc_equal(line,"JCI_SW_VER=\"MAZ_CMU-150_74.00.324\"")) ++v;
        if (oc_equal(line,"JCI_SW_VER_PATCH=\"A\"")) ++pa;
        if (oc_equal(line,"JCI_SW_FLAVOR=\"cmu150_NA\"")) ++fl;
    }
    return v==1 && pa==1 && fl==1;
}

static int oc_check_sha_file(int root, const char *rel, const char *expected) {
    long fd=oc_beneath(root,rel,OC_READ,0);
    if (fd<0) return 0;
    char digest[65]; OcMeta m;
    int ok=oc_hash_copy((int)fd,-1,33554432,digest,&m)==OC_COPY_OK && oc_equal(digest,expected);
    if (oc_close((int)fd)<0) ok=0;
    return ok;
}

static int oc_check_dir(int root, const char *rel) {
    long fd=oc_beneath(root,rel,OC_DIRECTORY,0);
    if (fd<0) return 0;
    OcMeta m;
    int ok=oc_stat((int)fd,&m)>=0 && (m.mode&OC_TYPE)==OC_DIR;
    if (oc_close((int)fd)<0) ok=0;
    return ok;
}

int oc_firmware_guard(int root, const char *op_tag, char *scratch, unsigned cap, const char **err_out) {
#ifdef OC_HOST
    if (getenv("OC_HOST_SKIP_FW_GUARD")) return 1;
#endif
    if (!oc_nonroot_allowed() && oc_owner()!=0) { *err_out="root_required"; return 0; }
    if (!oc_version_ok(root,scratch,cap)) { *err_out="unsupported_firmware"; return 0; }
    if (!op_tag || !oc_equal(op_tag,"settings:status:completion")) {
        if (!oc_check_sha_file(root,"jci/gui/framework/js/GuiFramework.js",
            oc_pin_digest("root/framework.js","ca2889f7cb0361610e57b43004572fdd53c00d1d3003409bb92c744fcb253f70"))) {
            *err_out="unsupported_framework"; return 0;
        }
        if (!oc_check_sha_file(root,"jci/lvds/lvds_service",
            oc_pin_digest("root/lvds-service","19a56b9e7b9f7399b152dbc7e8bd8de3fa01f154e45e8981becec6e96d3f70eb"))) {
            *err_out="unsupported_display"; return 0;
        }
    }
    if (!oc_mounts_scan(root,scratch,cap,1,1)) { *err_out="persistence_unavailable"; return 0; }
    if (!oc_check_dir(root,"tmp") || !oc_check_dir(root,"tmp/mnt") || !oc_check_dir(root,"tmp/mnt/data_persist")) {
        *err_out="invalid_persistence_path"; return 0;
    }
    if (!oc_mounts_scan(root,scratch,cap,1,0)) { *err_out="invalid_boot_mounts"; return 0; }
    return 1;
}
