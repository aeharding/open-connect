/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Authoritative OC1 durable transaction record parser and atomic publisher.
 */
#include "oc-core.h"

int oc_record_mode(OcBoot *b, const char *expected_before, const char *expected_after) {
    if (oc_text(b->data,"record",b->record,sizeof b->record,0)<0 || !oc_fields_line(b->record,b->record_fields,13)) return 0;
    char **f=b->record_fields;
    if (!oc_equal(f[0],"OC1")||!oc_hex(f[2],32)||!oc_hex(f[3],64)||!oc_hex(f[4],64)||!oc_hex(f[5],64)) return 0;
    for (unsigned i=6; i<=8; ++i) if (!oc_equal(f[i],"-")&&!oc_hex(f[i],64)) return 0;
    if (oc_length(f[9])!=1||f[9][0]<'0'||f[9][0]>'3') return 0;
    if ((!oc_equal(f[10],"-")&&!oc_uuid(f[10]))||(!oc_equal(f[11],"-")&&!oc_uuid(f[11]))) return 0;
    if (!(oc_equal(f[12],"-")||oc_equal(f[12],"installed")||oc_equal(f[12],"removed")||oc_equal(f[12],"undone")||oc_equal(f[12],"restart"))) return 0;
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

int oc_record_commit(OcBoot *b) {
    if (!oc_random(b->root,b->nonce)) return 0;
    b->record_fields[2]=b->nonce; b->record_fields[8]="-";
    b->next[0]=0;
    for (unsigned i=0; i<13; ++i)
        if (!oc_join(b->next,sizeof b->next,b->next,b->record_fields[i]) ||
            !oc_join(b->next,sizeof b->next,b->next,i==12?"\n":"|")) return 0;
    char name[64];
    if (!oc_join(name,sizeof name,"record.",b->nonce)) return 0;
    long fd=oc_openat(b->data,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,b->next,oc_length(b->next)) && oc_mode((int)fd,0600)>=0;
    oc_stamp(b,"record_written"); oc_cut("record_written");
    if (ok) ok=oc_sync((int)fd)>=0;
    oc_stamp(b,"record_synced"); oc_cut("record_synced");
    if (oc_close((int)fd)<0) ok=0;
    if (!ok) return 0;
    if (oc_rename(b->data,name,"record")<0) return 0;
    b->debited=1;
    oc_stamp(b,"record_renamed"); oc_cut("record_renamed");
    if (oc_sync(b->data)<0) return 0;
    oc_stamp(b,"directory_synced"); oc_cut("directory_synced");
    if (oc_text(b->data,"record",b->scratch,sizeof b->scratch,0)<0 || !oc_equal(b->scratch,b->next)) return 0;
    return 1;
}
