/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Authoritative OC1 durable transaction record parser and atomic publisher.
 * Shared by both boot-select (OcBoot) and api (lightweight buffer API).
 */
#include "oc-core.h"

int oc_record_parse_any(char *buf, char *f[13]) {
    if (!oc_fields_line(buf,f,13)) return 0;
    if (!oc_equal(f[0],"OC1")||!oc_hex(f[2],32)||!oc_hex(f[3],64)||!oc_hex(f[4],64)||!oc_hex(f[5],64)) return 0;
    int settled=oc_equal(f[1],"active")||oc_equal(f[1],"removed")||oc_equal(f[1],"purge");
    int pending=oc_equal(f[1],"install")||oc_equal(f[1],"set")||oc_equal(f[1],"uninstall")||oc_equal(f[1],"apply");
    if (!settled && !pending) return 0;
    if (settled) { if (!oc_equal(f[6],"-")||!oc_equal(f[7],"-")) return 0; }
    else { if (!oc_hex(f[6],64)||!oc_hex(f[7],64)) return 0; }
    if (!oc_equal(f[8],"-")&&!oc_hex(f[8],64)) return 0;
    if (f[9][1]||f[9][0]<'0'||f[9][0]>'3') return 0;
    if ((!oc_equal(f[10],"-")&&!oc_uuid(f[10]))||(!oc_equal(f[11],"-")&&!oc_uuid(f[11]))) return 0;
    if (!(oc_equal(f[12],"-")||oc_equal(f[12],"installed")||oc_equal(f[12],"removed")||
          oc_equal(f[12],"undone")||oc_equal(f[12],"restart"))) return 0;
    return 1;
}

int oc_record_read_any(int data_fd, long owner, long group, char *buf, unsigned cap, char *f[13]) {
    OcMeta m;
    long fd=oc_openat(data_fd,"record",OC_READ,0);
    if (fd<0) return 0;
    int ok=oc_stat((int)fd,&m)>=0 && m.mode==(OC_REGULAR|0600) &&
        m.uid==(unsigned)owner && m.gid==(unsigned)group;
    int n=ok?oc_text_fd((int)fd,buf,cap):-1;
    if (oc_close((int)fd)<0) ok=0;
    return ok && n>0 && oc_record_parse_any(buf,f);
}

int oc_record_write_atomic(int root_fd, int data_fd, char *f[13], char nonce_out[33]) {
    char nonce[33], next[1024], check[1024], name[64];
    if (!oc_random(root_fd,nonce)) return 0;
    if (nonce_out) for (unsigned i=0; i<33; ++i) nonce_out[i]=nonce[i];
    next[0]=0;
    for (unsigned i=0; i<13; ++i) {
        const char *val = (i==2) ? nonce : (i==8) ? "-" : f[i];
        if (!oc_join(next,sizeof next,next,val) ||
            !oc_join(next,sizeof next,next,i==12?"\n":"|")) return 0;
    }
    if (!oc_join(name,sizeof name,"record.",nonce)) return 0;
    long fd=oc_openat(data_fd,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,next,oc_length(next)) && oc_mode((int)fd,0600)>=0 && oc_sync((int)fd)>=0;
    if (oc_close((int)fd)<0) ok=0;
    if (!ok) { (void)oc_unlink(data_fd,name); return 0; }
    if (oc_rename(data_fd,name,"record")<0) { (void)oc_unlink(data_fd,name); return 0; }
    if (oc_sync(data_fd)<0) return 0;
    return oc_text(data_fd,"record",check,sizeof check,0)>0 && oc_equal(check,next);
}

int oc_record_file(OcBoot *b, const char *expected_before, const char *expected_after) {
    if (!oc_record_read_any(b->data,b->owner,b->group,b->record,sizeof b->record,b->record_fields)) return 0;
    char **f=b->record_fields;
    if (expected_after)
        return oc_equal(f[1],"set")&&oc_equal(f[5],expected_before)&&oc_equal(f[6],expected_before)&&oc_equal(f[7],expected_after);
    return oc_equal(f[1],"active")&&oc_equal(f[6],"-")&&oc_equal(f[7],"-")&&(!expected_before||oc_equal(f[5],expected_before));
}

int oc_read_boot_id(int ram, long owner, long group, char out[37]) {
    return oc_readlink_owned(ram,"boot-id",owner,group,out,37)==36 && oc_uuid(out);
}

int oc_boot_id_ensure(int root, int ram, char *const rec[13], long owner, long group, char out[37]) {
    if (oc_absent_at(ram,"boot-id")) {
        char kboot[40], dig[65];
        if (oc_text(root,"proc/sys/kernel/random/boot_id",kboot,sizeof kboot,1)<0 ||
            !oc_one_line(kboot) || !oc_uuid(kboot)) return 0;
        OcHash h; oc_hash_init(&h);
        const char *parts[5]={"OCBOOT1",kboot,rec[2],rec[11],rec[10]};
        for (unsigned i=0; i<5; ++i) {
            oc_hash_add(&h,parts[i],oc_length(parts[i]));
            oc_hash_add(&h,i==4?"\n":"|",1);
        }
        oc_hash_finish(&h,dig);
        unsigned at=0;
        for (unsigned i=0; i<36; ++i) out[i]=(i==8||i==13||i==18||i==23)?'-':dig[at++];
        out[36]=0;
        for (unsigned i=0; i<16; ++i) {
            if (!oc_equal(out,rec[11]) && !oc_equal(out,rec[10])) break;
            out[0]="0123456789abcdef"[i];
        }
        if (oc_symlink(out,ram,"boot-id")<0) return 0;
    }
    return oc_read_boot_id(ram,owner,group,out);
}
