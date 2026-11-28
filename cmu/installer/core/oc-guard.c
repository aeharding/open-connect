/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Shared exact-v74 firmware identity and physical mount guards.
 * Linked into both boot-select and api so mount and OEM attestation rules
 * have a single authoritative implementation.
 */
#include "oc-core.h"
#ifdef OC_HOST
#include <stdlib.h>
#endif

const char *const oc_root_names[19]={
    "sm.conf","sm_WCP.conf","board.sh","mmui.so","mmui.xml","uia.so","index.html",
    "system-app.js","settings-app.js","base-app.js","manager.so","device-master.xml",
    "eem.so","device-manager.so","rungetty","sshd","ssh-keygen","framework.js","lvds-service"
};
const char *const oc_root_paths[19]={
    "/jci/sm/sm.conf","/jci/sm/sm_WCP.conf","/jci/scripts/get_board_type.sh",
    "/jci/mmui/svcjcimmui.so","/jci/mmui/mmui_config.xml","/jci/mmui/uia/libjciuiasystem.so",
    "/jci/gui/index.html","/jci/gui/apps/system/js/systemApp.js",
    "/jci/gui/apps/syssettings/js/syssettingsApp.js","/jci/gui/framework/js/BaseApp.js",
    "/jci/lib/libjciuiamgr.so","/etc/devmgr_config_master.xml","/jci/vbs/modules/libjcimod_eem.so",
    "/jci/devicemanager/libdevicemanager.so","/usr/bin/rungetty","/usr/sbin/sshd","/usr/bin/ssh-keygen",
    "/jci/gui/framework/js/GuiFramework.js","/jci/lvds/lvds_service"
};
const char *const oc_root_digests[19]={
    "fa3484d7c644393ab6cb083990e483201129a207e7755459296dde8ec82a4d84",
    "92034449e76689b995fcd369d584f441829a0ee6e8d74c858cd92f4049f7b27d",
    "2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da",
    "034d5339116aa2f2da81ec6caaf3426081c452544f3b527af3a2121b7a7e0bca",
    "ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0",
    "32431c6b74c8ba531fcc10c50748075416e0f7dc1a3f903f182d816a0f3f5fc2",
    "b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420",
    "23106b04bd6bad514dd879b217a34a0f0289d58f86a0ae022488be6a022ca8e1",
    "a83dd588b54531475024b7cd048be1d0e11556abd68bbbcc334cc5ede7534cd1",
    "1489e544e483c878fa000be378a3bbb92dcc9965aadc5029a58f3fc1147337da",
    "1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29",
    "9f1811e2d9a905ba9060a9c20b8d91c18aaa5c079512e3261b51cf0114fc857b",
    "0160354861d0dddf09f05dc69df95f14be074de706a4d7656166666d587439d9",
    "88d6291d74fe993536ec724064b8ccfbc133b2341282b93cfc7fb2927fbbc563",
    "0b205e203510bef6d20b910f31c88a7f9c141048c41b1704eed20b880d67ac82",
    "f83f7661e0ba41da379936ba319f40e228cd14d470c3081f19d8fbec8297a195",
    "b735d7dd9a9a45badf18b2a9d0e32ca791a4e582400e57378a27b2a2d92ae9c9",
    "ca2889f7cb0361610e57b43004572fdd53c00d1d3003409bb92c744fcb253f70",
    "19a56b9e7b9f7399b152dbc7e8bd8de3fa01f154e45e8981becec6e96d3f70eb"
};
const char *const oc_orig_autostart_digest="a8d019650c2a17a50b5ff39435f916c2cbeb3556af128fd913b9714b380e06bd";
const char *const oc_composed_names[12]={
    "autostart","uia.so","mmui.so","mmui.xml","index-on.html","index-off.html",
    "sm-normal-on.conf","sm-normal-off.conf","sm-wcp-on.conf","sm-wcp-off.conf","vui.so","vui.xml"
};
const OcPin oc_touch_pins[2]={
    {"touch/devices/svc","/jci/devices/svc-com-jci-cpp-devices.so","e438bef5acb59c65c810df905488c7b1230cce88b20a295dc2da182f78da2695",1},
    {"touch/devices/lib","/jci/lib/libjcidevices.so","4d05f4242ffab8ed2e21c4785b077b7225ea54c3e62c8e02a26eb400eb6a1171",1}
};
const OcPin oc_base_pins[5]={
    {"base/settings.txt","/config/common/log/settings.txt","8c95ceaf213af1086e913fd78b69c9b00869c848375c3b40de3c36166d5d3ea0",0},
    {"base/libjcicommon.so","/jci/lib/libjcicommon.so","637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d",0},
    {"base/log-defaults.js","/jci/gui/common/js/logDefaults.js","83f5a71617f34427bb903c90ac5df53ed4e0e6437cca8a8bdb509909a324ba3a",0},
    {"base/vui/vui.so","/jci/vui/svcjcivui.so","ba72171a04dcc264ff5f690ac25ac2b009624158499159cdb6aebb08a9ab34f4",1},
    {"base/vui/vui.xml","/jci/vui/vui_config.xml","d2511533b59bc9773f92d8fff9cbcf591d9ff461c33839ff4eaaae6f5d0aaef0",1}
};

int oc_mounts_next(char **cursor, char *f[6]) {
    char *p=*cursor;
    if (!*p) return 0;
    unsigned n=0;
    while (*p && *p!='\n') {
        if (*p==' '||*p=='\t') { ++p; continue; }
        if (n==6) return -1;
        f[n++]=p;
        while (*p && *p!=' ' && *p!='\t' && *p!='\n') ++p;
        if (*p==' '||*p=='\t') *p++=0;
    }
    if (!*p || n!=6) return -1;
    *p++=0;
    *cursor=p;
    return 1;
}

static int oc_persist_rw_opts(const char *opts) {
    char options[256];
    if (!oc_join(options,sizeof options,",",opts)||!oc_join(options,sizeof options,options,",")) return 0;
    int rw=0;
    for (char *q=options; *q; ++q) if (oc_prefix(q,",rw,")) ++rw;
    return rw==1;
}

int oc_mounts_mode(int root, char *scratch, unsigned cap, int allow_rw) {
    if (oc_text(root,"proc/self/mounts",scratch,cap,1)<0) return 0;
    unsigned rcount=0, data=0, rootfs=0;
    char *p=scratch, *f[6]; int mr;
    while ((mr=oc_mounts_next(&p,f))>0) {
        if (oc_equal(f[1],"/")) {
            if (oc_equal(f[0],"rootfs")&&oc_equal(f[2],"rootfs")&&oc_equal(f[3],"rw")&&!rcount&&!rootfs) ++rootfs;
            else {
                int want_ok = allow_rw==2 ? oc_equal(f[3],"rw,noatime")
                    : (oc_equal(f[3],"ro,noatime")||(allow_rw&&oc_equal(f[3],"rw,noatime")));
                if (!oc_equal(f[0],"/dev/ffx01p1")||!oc_equal(f[2],"relfs")||!want_ok) return 0;
                ++rcount;
            }
        }
        if (oc_equal(f[1],"/tmp/mnt/data_persist")) {
            if (!oc_equal(f[0],"/dev/mmcblk0p2")||!oc_equal(f[2],"relfs")||!oc_persist_rw_opts(f[3])) return 0;
            ++data;
        }
        if (oc_equal(f[1],"/" OC_DATA)||oc_prefix(f[1],"/" OC_DATA "/")||
            oc_equal(f[1],"/" OC_RAM)||oc_prefix(f[1],"/" OC_RAM "/")) return 0;
    }
    return mr==0 && rcount==1 && data==1;
}

static int oc_mounts_persist_ok(int root, char *scratch, unsigned cap) {
    if (oc_text(root,"proc/self/mounts",scratch,cap,1)<0) return 0;
    unsigned data=0;
    char *p=scratch, *f[6]; int mr;
    while ((mr=oc_mounts_next(&p,f))>0) {
        if (oc_equal(f[1],"/tmp/mnt/data_persist") && oc_equal(f[0],"/dev/mmcblk0p2") &&
            oc_equal(f[2],"relfs") && oc_persist_rw_opts(f[3])) ++data;
    }
    return mr==0 && data==1;
}

int oc_version_text_ok(char *text) {
    unsigned v=0, pa=0, fl=0;
    char *p=text;
    while (*p) {
        char *line=p;
        while (*p && *p!='\n') ++p;
        if (!*p) return 0;
        *p++=0;
        if (oc_equal(line,"JCI_SW_VER=\"MAZ_CMU-150_74.00.324\"")) ++v;
        if (oc_equal(line,"JCI_SW_VER_PATCH=\"A\"")) ++pa;
        if (oc_equal(line,"JCI_SW_FLAVOR=\"cmu150_NA\"")) ++fl;
    }
    return v==1 && pa==1 && fl==1;
}

int oc_version_ok(int root, char *scratch, unsigned cap) {
    int n=oc_text(root,"jci/version.ini",scratch,cap,0);
    return n>0 && oc_version_text_ok(scratch);
}

OcDiag oc_diag;

void oc_diag_clear(void) {
    unsigned char *p=(unsigned char *)&oc_diag;
    for (unsigned i=0; i<sizeof oc_diag; ++i) p[i]=0;
}

static void oc_diag_cp(char *dst, unsigned cap, const char *s) {
    unsigned i=0;
    if (s) {
        for (; s[i] && i+1<cap; ++i) {
            unsigned char c=(unsigned char)s[i];
            dst[i]=(c>=32 && c<127 && c!='|') ? (char)c : '?';
        }
    }
    dst[i]=0;
}

void oc_diag_set(const char *step, const char *path, const char *reason,
                 const char *expected, const char *actual) {
    if (oc_diag.step[0]) return;
    oc_diag_cp(oc_diag.step,sizeof oc_diag.step,step);
    oc_diag_cp(oc_diag.path,sizeof oc_diag.path,path);
    oc_diag_cp(oc_diag.reason,sizeof oc_diag.reason,reason);
    oc_diag_cp(oc_diag.expected,sizeof oc_diag.expected,expected);
    oc_diag_cp(oc_diag.actual,sizeof oc_diag.actual,actual);
}

static int oc_check_sha_file(int root, const char *rel, const char *expected) {
    long fd=oc_beneath(root,rel,OC_READ,0);
    char full[128]; full[0]=0; (void)oc_join(full,sizeof full,"/",rel);
    if (fd<0) {
        oc_diag_set("firmware_guard",full,fd==-2?"missing":"unreadable",expected,0);
        return 0;
    }
    char digest[65]; OcMeta m;
    int hr=oc_hash_copy((int)fd,-1,33554432,digest,&m);
    int ok=hr==OC_COPY_OK && oc_equal(digest,expected);
    if (oc_close((int)fd)<0) ok=0;
    if (!ok) oc_diag_set("firmware_guard",full,hr==OC_COPY_OK?"sha256_mismatch":"unreadable",
                         expected,hr==OC_COPY_OK?digest:0);
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
    if (!oc_version_ok(root,scratch,cap)) {
        oc_diag_set("firmware_guard","/jci/version.ini","version_mismatch",0,0);
        *err_out="unsupported_firmware"; return 0;
    }
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
    if (!oc_mounts_persist_ok(root,scratch,cap)) {
        oc_diag_set("firmware_guard","/proc/self/mounts","persistence_mount",0,0);
        *err_out="persistence_unavailable"; return 0;
    }
    if (!oc_check_dir(root,"tmp") || !oc_check_dir(root,"tmp/mnt") || !oc_check_dir(root,"tmp/mnt/data_persist")) {
        oc_diag_set("firmware_guard","/tmp/mnt/data_persist","invalid_directory",0,0);
        *err_out="invalid_persistence_path"; return 0;
    }
    if (!oc_mounts_mode(root,scratch,cap,1)) {
        oc_diag_set("firmware_guard","/proc/self/mounts","boot_mounts",0,0);
        *err_out="invalid_boot_mounts"; return 0;
    }
    return 1;
}
