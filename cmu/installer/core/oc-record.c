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
    if (oc_length(f[9])!=1||f[9][0]<'0'||f[9][0]>'3') return 0;
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

int oc_record_mode(OcBoot *b, const char *expected_before, const char *expected_after) {
    if (oc_text(b->data,"record",b->record,sizeof b->record,0)<0 || !oc_record_parse_any(b->record,b->record_fields)) return 0;
    char **f=b->record_fields;
    if (expected_after)
        return oc_equal(f[1],"set")&&oc_equal(f[5],expected_before)&&oc_equal(f[6],expected_before)&&oc_equal(f[7],expected_after);
    return oc_equal(f[1],"active")&&oc_equal(f[6],"-")&&oc_equal(f[7],"-")&&(!expected_before||oc_equal(f[5],expected_before));
}

int oc_record(OcBoot *b) { return oc_record_mode(b,0,0); }

int oc_record_file(OcBoot *b, const char *expected_before, const char *expected_after) {
    OcMeta record_meta;
    long record=oc_openat(b->data,"record",OC_READ,0);
    if (record<0) return 0;
    int ok=oc_stat((int)record,&record_meta)>=0 && record_meta.mode==(OC_REGULAR|0600) &&
        record_meta.uid==(unsigned)b->owner && record_meta.gid==(unsigned)b->group;
    if (oc_close((int)record)<0) ok=0;
    return ok && oc_record_mode(b,expected_before,expected_after);
}
