/* SPDX-License-Identifier: AGPL-3.0-or-later
 * OCBP1 plan parsing/sealing, mount checks, and full dependency/snapshot/access/identity coverage.
 */
#include "oc-core.h"

unsigned oc_meta_text(char *p, const OcMeta *m) {
    oc_u64 values[10]={m->device,m->inode,m->size,m->mode,m->uid,m->gid,
                       m->modified,m->modified_ns,m->changed,m->changed_ns};
    unsigned n=0;
    for (unsigned i=0; i<10; ++i) {
        unsigned width=(i<3||i==6||i==8)?16:8;
        p[n++]='|'; oc_put_hex(p+n,values[i],width); n+=width;
    }
    p[n]=0;
    return n;
}

int oc_meta_parse(char **fields, OcMeta *m) {
    oc_u64 values[10];
    for (unsigned i=0; i<10; ++i) {
        unsigned width=(i<3||i==6||i==8)?16:8;
        if (!oc_hex(fields[i],width)) return 0;
        values[i]=oc_get_hex(fields[i],width);
    }
    m->device=values[0]; m->inode=values[1]; m->size=values[2];
    m->mode=(oc_u32)values[3]; m->uid=(oc_u32)values[4]; m->gid=(oc_u32)values[5];
    m->modified=values[6]; m->modified_ns=(oc_u32)values[7];
    m->changed=values[8]; m->changed_ns=(oc_u32)values[9];
    return (m->mode&OC_TYPE)==OC_REGULAR && m->modified_ns<1000000000 && m->changed_ns<1000000000;
}

int oc_line(OcLines *r, char output[OC_LINE_SIZE]) {
    unsigned n=0;
    for (;;) {
        if (r->at==r->filled) {
            long got=oc_read(r->fd,r->bytes,sizeof r->bytes);
            if (got==-4) continue;
            if (got<0) return -1;
            if (!got) return n?-1:0;
            r->at=0; r->filled=(unsigned)got;
        }
        unsigned char c=(unsigned char)r->bytes[r->at++];
        if (++r->total>OC_PLAN_LIMIT) return -1;
        if (c=='\n') { output[n]=0; return n?1:-1; }
        if (c<=32 || c>=127 || n+1>=OC_LINE_SIZE) return -1;
        output[n++]=(char)c;
    }
}

int oc_plan_rows(int root, int snapshot, int input, int output, int mode) {
    int sealing=mode==1;
    OcLines reader;
    char line[OC_LINE_SIZE], original[OC_LINE_SIZE], seen[OC_PLAN_ROWS][192];
    char *fields[13], digest[65], meta[131];
    unsigned count=0, n;
    reader.at=reader.filled=reader.total=0; reader.fd=input;
    int status=oc_line(&reader,line);
    if (status!=1) return 0;
    n=oc_fields(line,fields,13);
    if (n!=3 || !oc_equal(fields[0],"OCBP1") || !oc_hex(fields[1],64) || !oc_hex(fields[2],64)) return 0;
    if (sealing) {
        char hdr[160];
        if (!oc_join4(hdr,sizeof hdr,"OCBP1|",fields[1],"|",fields[2]) ||
            !oc_join(hdr,sizeof hdr,hdr,"\n") || !oc_write_all(output,hdr,oc_length(hdr))) return 0;
    }
    while ((status=oc_line(&reader,line))==1) {
        unsigned length=oc_length(line);
        for (unsigned i=0; i<=length; ++i) original[i]=line[i];
        n=oc_fields(line,fields,13);
        if (n!=(sealing?3u:13u) || !oc_key(fields[0]) ||
            (!oc_equal(fields[2],"-")&&!oc_hex(fields[2],64)) || count==OC_PLAN_ROWS) return 0;
        const char *path=fields[1];
        int parent=root;
        if (path[0]=='@'&&path[1]=='/') { parent=snapshot; path+=2; }
        else if (path[0]=='/') ++path;
        else return 0;
        if (!oc_key(path)) return 0;
        for (unsigned i=0; i<count; ++i) if (oc_equal(seen[i],fields[0])) return 0;
        for (unsigned i=0;; ++i) { seen[count][i]=fields[0][i]; if (!fields[0][i]) break; }
        ++count;
        if (oc_equal(fields[2],"-")) {
            if (!oc_absent_at(parent,path)) return 0;
            if (!sealing) {
                for (unsigned i=3; i<13; ++i) if (!oc_equal(fields[i],"-")) return 0;
            } else if (!oc_write_all(output,original,length) || !oc_write_all(output,"|-|-|-|-|-|-|-|-|-|-\n",21)) return 0;
            continue;
        }
        long fd=oc_beneath(parent,path,OC_READ,0);
        if (fd<0) return 0;
        OcMeta current, expected;
        int ok;
        if (sealing) {
            ok=oc_hash_copy((int)fd,-1,33554432,digest,&current)==OC_COPY_OK && oc_equal(digest,fields[2]);
        } else if (mode==2) {
            ok=oc_meta_parse(fields+3,&expected) &&
                oc_hash_copy((int)fd,-1,33554432,digest,&current)==OC_COPY_OK && oc_equal(digest,fields[2]) &&
                oc_meta_resealable(&expected,&current);
        } else {
            ok=oc_meta_parse(fields+3,&expected) && oc_stat((int)fd,&current)>=0 &&
                oc_meta_row_equal(fields[0],&expected,&current);
        }
        if (oc_close((int)fd)<0) ok=0;
        if (!ok) return 0;
        if (oc_prefix(fields[0],"base/vui/")||oc_prefix(fields[0],"touch/devices/")) {
            OcMeta stock;
            if (!oc_stock_meta(root,&stock) || current.device!=stock.device) return 0;
        }
        if (sealing) {
            n=oc_meta_text(meta,&current);
            if (!oc_write_all(output,original,length) || !oc_write_all(output,meta,n) || !oc_write_all(output,"\n",1)) return 0;
        }
    }
    return status==0 && count>0;
}

int oc_mounts(OcBoot *b) { return oc_mounts_mode(b->root,b->scratch,sizeof b->scratch,0); }

int oc_input_mode(OcInput *input, const char *text) {
    unsigned mode, uid, gid;
    return !input->absent && oc_metadata_mode(text,&mode,&uid,&gid) &&
        input->meta.mode==(OC_REGULAR|mode) && input->meta.uid==uid && input->meta.gid==gid;
}

OcInput *oc_find(OcBoot *b, const char *key) {
    for (unsigned i=0; i<b->input_count; ++i) if (oc_equal(b->inputs[i].key,key)) return &b->inputs[i];
    return 0;
}

OcInput *oc_expect(OcBoot *b, const char *key, const char *path, const char *digest) {
    OcInput *row=oc_find(b,key);
    if (!row||row->used||!oc_equal(row->path,path)||!oc_equal(row->digest,digest)) return 0;
    row->used=1;
    return row;
}

int oc_plan(OcBoot *b) {
    if (!oc_saved_text(b->snapshot,&b->current,"boot.plan",b->plan_text,sizeof b->plan_text)) return 0;
    char *p=b->plan_text, *fields[13];
    unsigned rows=0;
    while (*p) {
        char *line=p;
        while (*p && *p!='\n') ++p;
        if (!*p) return 0;
        *p++=0;
        unsigned n=oc_fields(line,fields,13);
        if (!rows++) {
            if (n!=3||!oc_equal(fields[0],"OCBP1")||!oc_equal(fields[1],b->record_fields[4])||!oc_equal(fields[2],b->record_fields[3])) return 0;
            continue;
        }
        if (n!=13||b->input_count==OC_PLAN_ROWS||!oc_key(fields[0])||oc_find(b,fields[0])) return 0;
        OcInput *row=&b->inputs[b->input_count++];
        row->key=fields[0]; row->path=fields[1]; row->digest=fields[2]; row->used=0;
        row->absent=oc_equal(fields[2],"-");
        int parent=b->root;
        const char *path=fields[1];
        if (oc_prefix(path,"@/")) { parent=b->snapshot; path+=2; }
        else if (*path=='/') ++path;
        else return 0;
        if (!oc_key(path)) return 0;
        if (row->absent) {
            for (unsigned i=3; i<13; ++i) if (!oc_equal(fields[i],"-")) return 0;
            if (!oc_absent_at(parent,path)) return 0;
        } else {
            if (!oc_hex(fields[2],64)||!oc_meta_parse(fields+3,&row->meta)) return 0;
            long fd=oc_beneath(parent,path,OC_READ,0);
            if (fd<0) {
                if (fd==-2&&(b->touch_drift&1)&&oc_prefix(row->key,"touch/devices/")) { b->touch_drift|=2; continue; }
                return 0;
            }
            OcMeta actual;
            int ok=oc_stat((int)fd,&actual)>=0;
            if (oc_close((int)fd)<0) ok=0;
            if (!ok) return 0;
            if (!oc_meta_row_equal(row->key,&row->meta,&actual)) {
                if ((b->touch_drift&1)&&oc_prefix(row->key,"touch/devices/")) { b->touch_drift|=2; continue; }
                if (!b->gated||!oc_meta_resealable(&row->meta,&actual)) return 0;
                row->meta=actual; b->metadata_drift=1;
            }
        }
    }
    return rows>1;
}

int oc_expected_members(OcBoot *b, OcManifest *manifest, const char *key_prefix, const char *path_prefix) {
    char key[192], path[192];
    for (unsigned i=0; i<manifest->count; ++i) {
        OcMember *m=&manifest->rows[i];
        if (!oc_join(key,sizeof key,key_prefix,m->name)||!oc_join(path,sizeof path,path_prefix,m->name)||
            !oc_expect(b,key,path,m->digest)) return 0;
    }
    return 1;
}

int oc_dependency_coverage(OcBoot *b) {
    OcManifest dependencies;
    char name[192], path[192], scope[96], prefix[192];
    if (!oc_saved_text(b->snapshot,&b->current,"dependencies",b->dependencies,sizeof b->dependencies)||
        !oc_manifest(b->dependencies,&dependencies,1)) return 0;
    unsigned expected=sizeof oc_root_names/sizeof *oc_root_names + b->pkg.count+1+b->composition.count+1;
    if (dependencies.count!=expected) return 0;
    for (unsigned i=0; i<sizeof oc_root_names/sizeof *oc_root_names; ++i) {
        if (!oc_join(name,sizeof name,"root/",oc_root_names[i])) return 0;
        const char *digest=oc_digest(&dependencies,name);
        if (!digest||!oc_expect(b,name,oc_root_paths[i],digest)) return 0;
        if (oc_equal(oc_root_names[i],"manager.so")&&
            !oc_equal(digest,oc_pin_digest("manager.so","1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29"))) return 0;
    }
    for (unsigned kind=0; kind<2; ++kind) {
        OcManifest *m=kind?&b->composition:&b->pkg;
        if (!oc_join4(scope,sizeof scope,kind?"composed-":"package-",b->record_fields[3],"/",0)||
            !oc_join4(prefix,sizeof prefix,kind?"/" OC_DATA "/composed/":"/" OC_DATA "/packages/",b->record_fields[3],"/",0)) return 0;
        for (unsigned i=0; i<=m->count; ++i) {
            const char *leaf=i==m->count?"files.sha256":m->rows[i].name;
            const char *digest=i==m->count?(kind?b->composed_digest:b->record_fields[3]):m->rows[i].digest;
            if (!oc_join(name,sizeof name,scope,leaf)||!oc_join(path,sizeof path,prefix,leaf)) return 0;
            const char *recorded=oc_digest(&dependencies,name);
            if (!recorded||!oc_equal(recorded,digest)||!oc_expect(b,name,path,digest)) return 0;
        }
    }
    return 1;
}

int oc_snapshot_coverage(OcBoot *b) {
    char key[192], path[192];
    static const char *const required[]={"autostart","config","dependencies","selector","sm-normal.conf","sm-wcp.conf","index.html","boot.plan","mmui.xml","vui-plugins.list"};
    if (b->current.count!=(b->access_present?13u:10u)) return 0;
    for (unsigned i=0; i<sizeof required/sizeof *required; ++i) if (!oc_digest(&b->current,required[i])) return 0;
    for (unsigned i=0; i<b->current.count; ++i) {
        OcMember *m=&b->current.rows[i];
        if (oc_equal(m->name,"boot.plan")) continue;
        if (!oc_join(key,sizeof key,"current/",m->name)||!oc_join(path,sizeof path,"@/",m->name)||
            !oc_expect(b,key,path,m->digest)) return 0;
    }
    if (!oc_join4(path,sizeof path,"/" OC_DATA "/snapshots/",b->record_fields[4],"/",0)) return 0;
    if (!oc_expected_members(b,&b->base,"baseline/",path)) return 0;
    if (!oc_join(path,sizeof path,path,"files.sha256")||
        !oc_expect(b,"baseline/files.sha256",path,b->record_fields[4])) return 0;
    unsigned base_count=3+(b->base_access_present?3:0)+(oc_digest(&b->base,"selector")?1:0);
    if (b->base.count!=base_count||!oc_digest(&b->base,"autostart")||!oc_digest(&b->base,"dependencies")) return 0;
    OcInput *row=oc_expect(b,"target/autostart","/usr/bin/autostart",oc_digest(&b->current,"autostart"));
    if (!row||!oc_input_mode(row,b->flags[4])) return 0;
    char *selector[3];
    if (!oc_saved_text(b->snapshot,&b->current,"selector",b->selector,sizeof b->selector)||
        !oc_fields_line(b->selector,selector,3)||!oc_hex(selector[0],64)||
        !oc_equal(selector[2],b->record_fields[3])||!oc_equal(selector[0],oc_digest(&b->pkg,"boot-select"))) return 0;
    unsigned mode, uid, gid;
    if (!oc_metadata_mode(selector[1],&mode,&uid,&gid)||mode!=0700||uid!=(unsigned)b->owner||gid!=(unsigned)b->group) return 0;
    row=oc_expect(b,"target/boot-select","/usr/bin/open-connect-boot-select",selector[0]);
    if (!row||!oc_input_mode(row,selector[1])) return 0;
    if (oc_digest(&b->base,"selector")) {
        if (!oc_saved_text(b->baseline,&b->base,"selector",b->scratch,sizeof b->scratch)||!oc_equal(b->scratch,"-\n")) return 0;
    }
    return 1;
}

int oc_access_coverage(OcBoot *b) {
    if (!b->access_present) return !b->base_access_present;
    if (!b->base_access_present) return 0;
    char **f=b->access_fields, **base=b->base_access_fields, path[192];
    OcInput *login=oc_expect(b,"target/runlogin","/usr/bin/runlogin",oc_digest(&b->current,"runlogin"));
    OcInput *ssh=oc_expect(b,"target/sshd.conf","/etc/ssh/sshd_config",oc_digest(&b->current,"sshd.conf"));
    if (!login||!ssh||!oc_input_mode(login,f[3])||!oc_input_mode(ssh,f[4])||!oc_equal(f[5],base[5])) return 0;
    if (!oc_equal(f[5],"-")) {
        oc_u64 inode;
        if (!oc_decimal(f[5],&inode)||!oc_join(path,sizeof path,"/usr/bin/.open-connect-runlogin-",f[5])) return 0;
        OcInput *hold=oc_find(b,"hold/runlogin");
        if (!hold||hold->used||!oc_equal(hold->path,path)) return 0;
        hold->used=1;
        const char *original=oc_digest(&b->base,"runlogin");
        if (!hold->absent && (!oc_equal(hold->digest,original)||hold->meta.inode!=inode||
            hold->meta.device!=login->meta.device||!oc_input_mode(hold,base[3]))) return 0;
        if (oc_equal(login->digest,original)) { if (login->meta.inode!=inode) return 0; }
        else if (hold->absent) return 0;
    }
    if (!oc_equal(f[2],"-")) {
        long keys=oc_open_private(b->data,"keys");
        if (keys<0||oc_close((int)keys)<0) return 0;
        if (!oc_join4(path,sizeof path,"/" OC_DATA "/keys/",f[2],".cmu",0)) return 0;
        OcInput *key=oc_expect(b,"key/owner",path,f[2]);
        if (!key||key->absent||key->meta.mode!=(OC_REGULAR|0600)||
            key->meta.uid!=(unsigned)b->owner||key->meta.gid!=(unsigned)b->group) return 0;
    }
    return 1;
}

int oc_identity_coverage(OcBoot *b) {
    OcInput *version=oc_find(b,"guard/version.ini");
    if (!version||version->used||!oc_equal(version->path,"/jci/version.ini")||version->absent||
        !oc_verified_text(b->root,"jci/version.ini",version->digest,b->scratch,sizeof b->scratch)) return 0;
    version->used=1;
    static const char *const values[]={"JCI_SW_VER=\"MAZ_CMU-150_74.00.324\"","JCI_SW_VER_PATCH=\"A\"","JCI_SW_FLAVOR=\"cmu150_NA\""};
    unsigned found[3]={0,0,0}; char *p=b->scratch;
    while (*p) {
        char *line=p;
        while (*p && *p!='\n') ++p;
        if (!*p) return 0;
        *p++=0;
        for (unsigned i=0; i<3; ++i) if (oc_equal(line,values[i])) ++found[i];
    }
    if (found[0]!=1||found[1]!=1||found[2]!=1) return 0;
    if (oc_equal(b->flags[1],"2")) {
        OcMeta stock;
        if (!oc_stock_meta(b->root,&stock)) return 0;
        for (unsigned i=0; i<2; ++i) {
            OcInput *row=oc_expect(b,oc_touch_pins[i].key,oc_touch_pins[i].path,
                                   oc_pin_digest(oc_touch_pins[i].key,oc_touch_pins[i].digest));
            if (!row||row->absent||(!(b->touch_drift&2)&&row->meta.device!=stock.device)) return 0;
        }
    }
    if (oc_equal(b->flags[6],"1")) {
        OcMeta stock;
        if (!oc_stock_meta(b->root,&stock)) return 0;
        for (unsigned i=0; i<b->input_count; ++i)
            if (oc_prefix(b->inputs[i].key,"base/vui/")&&b->inputs[i].meta.device!=stock.device) return 0;
        for (unsigned i=0; i<5; ++i)
            if (!oc_expect(b,oc_base_pins[i].key,oc_base_pins[i].path,
                           oc_pin_digest(oc_base_pins[i].key,oc_base_pins[i].digest))) return 0;
    }
    b->plugins=b->dependencies;
    if (!oc_saved_text(b->snapshot,&b->current,"vui-plugins.list",b->plugins,4096)) return 0;
    char *plugin=b->plugins; unsigned count=0;
    while (*plugin) {
        char *name=plugin;
        while (*plugin&&*plugin!='\n') ++plugin;
        if (!*plugin) return 0;
        *plugin++=0;
        if (!oc_equal(b->flags[6],"1")||!oc_key(name)||++count>48) return 0;
        for (const char *q=name; *q; ++q) if (*q=='/') return 0;
        char key[192], path[192];
        if (!oc_join(key,sizeof key,"base/vui/",name)||!oc_join(path,sizeof path,"/jci/vui/plugins/",name)) return 0;
        OcInput *row=oc_find(b,key);
        if (!row||!oc_hex(row->digest,64)||!oc_expect(b,key,path,row->digest)) return 0;
    }
    if (oc_equal(b->flags[6],"1")&&count<36) return 0;
    for (unsigned i=0; i<b->input_count; ++i) if (!b->inputs[i].used) return 0;
    return 1;
}
