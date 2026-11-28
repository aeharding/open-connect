/* SPDX-License-Identifier: AGPL-3.0-or-later
 * OC2 active preference decoder, 5-field stock baseline decoder, access metadata,
 * NVRAM reader, and VUI module pin lookup.
 */
#include "oc-core.h"

int oc_bit(const char *p) { return oc_equal(p,"0")||oc_equal(p,"1"); }
int oc_nvram_value(const char *p) { return oc_equal(p,"absent")||oc_equal(p,"enable")||oc_equal(p,"disable"); }

int oc_metadata_mode(const char *text, unsigned *mode, unsigned *uid, unsigned *gid) {
    unsigned values[3]={0,0,0}, field=0, n=0;
    while (*text) {
        unsigned c=(unsigned char)*text++;
        if (c==':') { if (!n||field==2) return 0; ++field; n=0; continue; }
        unsigned base=field?10:8;
        if (c<'0'||c>='0'+base||++n>(field?10u:4u)) return 0;
        if (field ? (values[field]>429496729u||(values[field]==429496729u&&c>'5')) : values[field]>0x1fffffffu) return 0;
        values[field]=values[field]*base+c-'0';
    }
    if (field!=2||!n||values[0]>07777) return 0;
    *mode=values[0]; *uid=values[1]; *gid=values[2]; return 1;
}

int oc_order(const char *a, const char *b) {
    while (*a && *a==*b) { ++a; ++b; }
    return (unsigned char)*a-(unsigned char)*b;
}

static int oc_service_id(const char *p) {
    unsigned n=0;
    if (*p<'a'||*p>'z') return 0;
    static const char *const reserved[]={"touch","warning","base","wireless","uart","ssh","carplay-autoshow","source-order","menu-loop","hold-scroll"};
    for (unsigned i=0; i<sizeof reserved/sizeof *reserved; ++i) if (oc_equal(p,reserved[i])) return 0;
    while (*p) {
        unsigned c=(unsigned char)*p++;
        if (++n>32||!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-')) return 0;
    }
    return n>0;
}

static int oc_service_keys(char *text, char **ids, unsigned *count) {
    *count=0;
    while (*text) {
        char *id=text;
        while (*text && *text!=',') ++text;
        if (*text) { *text++=0; if (!*text) return 0; }
        if (*count==16||!oc_service_id(id)||(*count && oc_order(id,ids[*count-1])<=0)) return 0;
        ids[(*count)++]=id;
    }
    return *count>0;
}

static int oc_oc2_decode(char *text, int active, OcPrefs *out, char svc_digest[65]) {
    unsigned mode, uid, gid;
    out->is_oc2=0; out->has_autoshow=0; out->has_source_order=0; out->has_menu_loop=0; out->has_hold_scroll=0; out->svc_count=0;
    out->package="-"; out->touch="0"; out->warning="0"; out->nvram="absent";
    out->metadata=""; out->base="0"; out->wireless="0"; out->autoshow="0"; out->source_order="0";
    out->menu_loop="0"; out->hold_scroll="0"; out->pandora="1";
    if (svc_digest) svc_digest[0]=0;
    if (!oc_prefix(text,"OC2\n")) {
        char *f[5];
        if (active || !oc_one_line(text) || oc_fields(text,f,5)!=5 || !oc_equal(f[0],"-")) return 0;
        if (!oc_bit(f[1])||!oc_bit(f[2])||!oc_nvram_value(f[3])||!oc_metadata_mode(f[4],&mode,&uid,&gid)) return 0;
        out->package=f[0]; out->touch=f[1]; out->warning=f[2]; out->nvram=f[3]; out->metadata=f[4];
        return 1;
    }
    if (!active) return 0;
    out->is_oc2=1;
    char *ids[16]; unsigned count=0, seen=0, service_seen=0;
    static const char *const keys[11]={
        "carplay-autoshow","source-order","menu-loop","hold-scroll",
        "package","touch","warning","nvram","metadata","base","wireless"
    };
    char **vals[11]={
        &out->autoshow,&out->source_order,&out->menu_loop,&out->hold_scroll,
        &out->package,&out->touch,&out->warning,&out->nvram,&out->metadata,&out->base,&out->wireless
    };
    int *opt_has[4]={&out->has_autoshow,&out->has_source_order,&out->has_menu_loop,&out->has_hold_scroll};
    char *previous="", *p=text+4;
    OcHash sh;
    if (svc_digest) oc_hash_init(&sh);
    while (*p) {
        char *key=p, *value=0;
        while (*p && *p!='\n') {
            if ((unsigned char)*p<32 || (unsigned char)*p==127) return 0;
            if (*p=='=') { if (value) return 0; *p=0; value=p+1; }
            ++p;
        }
        if (!*p || !value || !*value) return 0;
        *p++=0;
        if (oc_order(key,previous)<=0) return 0;
        previous=key;
        if (oc_equal(key,"service-ids")) {
            if (svc_digest) { oc_hash_add(&sh,value,oc_length(value)); oc_hash_add(&sh,"\n",1); }
            if (!oc_service_keys(value,ids,&count)) return 0;
            seen|=128; continue;
        }
        unsigned found=0;
        for (unsigned i=0; i<11; ++i) if (oc_equal(key,keys[i])) {
            if (i<4) { if (!oc_bit(value)) return 0; *opt_has[i]=1; }
            else seen|=1u<<(i-4);
            *vals[i]=value; found=1; break;
        }
        if (found) continue;
        if (!oc_prefix(key,"service.") || !oc_bit(value)) return 0;
        for (unsigned i=0; i<count; ++i) if (oc_equal(key+8,ids[i])) {
            service_seen|=1u<<i; found=1;
            out->svc_ids[i]=ids[i]; out->svc_vals[i]=value;
            if (svc_digest) { oc_hash_add(&sh,key,oc_length(key)); oc_hash_add(&sh,value,1); }
            if (oc_equal(ids[i],"pandora")) out->pandora=value;
            break;
        }
        if (!found) return 0;
    }
    if (svc_digest) oc_hash_finish(&sh,svc_digest);
    out->svc_count=count;
    return seen==255 && service_seen==((1u<<count)-1) && oc_hex(out->package,64) &&
        (oc_bit(out->touch)||oc_equal(out->touch,"2")) && oc_bit(out->warning) &&
        oc_nvram_value(out->nvram) && oc_metadata_mode(out->metadata,&mode,&uid,&gid) &&
        oc_bit(out->base) && oc_bit(out->wireless);
}

int oc_config(char *text, char **f, int active, char svc_digest[65]) {
    for (unsigned i=8; i<12; ++i) f[i]="0";
    OcPrefs p;
    if (!oc_oc2_decode(text,active,&p,svc_digest)) return 0;
    f[0]=p.package; f[1]=p.touch; f[2]=p.warning; f[3]=p.nvram; f[4]=p.metadata;
    if (active) {
        f[5]=p.pandora; f[6]=p.base; f[7]=p.wireless;
        f[8]=p.autoshow; f[9]=p.source_order; f[10]=p.menu_loop; f[11]=p.hold_scroll;
    }
    return 1;
}

int oc_access(char *text, char **fields) {
    if (!oc_one_line(text)) return 0;
    unsigned n=oc_fields(text,fields,6);
    if (n==5) fields[5]="-";
    else if (n!=6) return 0;
    if (!oc_bit(fields[0])||!oc_bit(fields[1])||(!oc_equal(fields[2],"-")&&!oc_hex(fields[2],64))) return 0;
    if (oc_equal(fields[1],"1")&&!oc_hex(fields[2],64)) return 0;
    for (unsigned i=3; i<5; ++i) {
        unsigned mode, uid, gid;
        if (!oc_metadata_mode(fields[i],&mode,&uid,&gid)) return 0;
    }
    if (!oc_equal(fields[5],"-")) {
        oc_u64 ino=0;
        if (!oc_decimal(fields[5],&ino)) return 0;
    }
    return 1;
}

int oc_nvram_at(int root, char value[16]) {
    long parent=oc_openat(root,"sys/class/nvram/nv-config/keys",OC_DIRECTORY,0);
    if (parent<0) return 0;
    long fd=oc_openat((int)parent,"lvds_speed_restriction",OC_READ,0);
    int ok=0;
    if (fd==-2) ok=oc_join(value,16,"","absent");
    else if (fd>=0) {
        OcMeta metadata;
        unsigned n=0;
        int read_ok=oc_stat((int)fd,&metadata)>=0 && (metadata.mode&OC_TYPE)==OC_REGULAR;
        while (read_ok && n<15) {
            long got=oc_read((int)fd,value+n,15-n);
            if (got==-4) continue;
            if (got<0) { read_ok=0; break; }
            if (!got) break;
            n+=(unsigned)got;
        }
        if (n && value[n-1]==0) --n;
        if (n && value[n-1]=='\n') --n;
        value[n]=0;
        ok=read_ok && oc_length(value)==n && (oc_equal(value,"enable")||oc_equal(value,"disable"));
        if (oc_close((int)fd)<0) ok=0;
    }
    if (oc_close((int)parent)<0) ok=0;
    return ok;
}

int oc_lookup_vui_pin(const char *modules, const char *plugin, char out[65]) {
    unsigned hits=0;
    const char *p=modules;
    while (*p) {
        const char *line=p;
        while (*p && *p!='\n') ++p;
        if (!*p) return 0;
        const char *end=p++;
        if (line==end || *line=='#') continue;
        const char *f[4]; unsigned flen[4]; unsigned nf=0;
        const char *q=line;
        for (const char *c=line; c<=end; ++c) if (c==end||*c=='\t') {
            if (nf==4) return 0;
            f[nf]=q; flen[nf]=(unsigned)(c-q); ++nf; q=c+1;
        }
        if (nf!=4) return 0;
        if (flen[0]==3 && f[0][0]=='v' && f[0][1]=='u' && f[0][2]=='i' &&
            flen[1]==oc_length(plugin) && flen[3]==64) {
            unsigned match=1;
            for (unsigned i=0; i<flen[1]; ++i) if (f[1][i]!=plugin[i]) { match=0; break; }
            if (match) {
                for (unsigned i=0; i<64; ++i) out[i]=f[3][i];
                out[64]=0;
                if (!oc_hex(out,64)) return 0;
                ++hits;
            }
        }
    }
    return hits==1;
}

int oc_no_cntrl(const char *p) {
    for (; *p; ++p) if ((unsigned char)*p<32 || (unsigned char)*p==127) return 0;
    return 1;
}

static int oc_member_name_ok(const char *p) {
    unsigned n=0;
    if (!((*p>='A'&&*p<='Z')||(*p>='a'&&*p<='z')||*p=='_')) return 0;
    for (; *p; ++p) {
        if (++n>64 || !((*p>='A'&&*p<='Z')||(*p>='a'&&*p<='z')||(*p>='0'&&*p<='9')||*p=='_')) return 0;
    }
    return n>0;
}

int oc_catalog_load(char *text, unsigned bytes, OcCatalog *cat) {
    cat->count=0;
    if (bytes>16384) return 0;
    char *seen_members[128]; unsigned mcount=0;
    char *p=text; unsigned counted=0;
    while (*p) {
        char *line=p;
        while (*p && *p!='\n') ++p;
        if (!*p) return 0;
        *p++=0;
        unsigned llen=oc_length(line);
        counted+=llen+1;
        if (!llen || line[0]=='#') continue;
        if (!oc_no_cntrl(line)) return 0;
        char *cols[6];
        if (oc_fields(line,cols,6)!=6) return 0;
        if (!oc_service_id(cols[0]) || cat->count==16) return 0;
        if (cat->count && oc_order(cols[0],cat->rows[cat->count-1].id)<=0) return 0;
        if (!*cols[1] || oc_length(cols[1])>64 || !oc_bit(cols[2]) ||
            !*cols[4] || oc_length(cols[4])>256 || !*cols[5] || oc_length(cols[5])>256) return 0;
        /* Validate SM member list: 1..8 space-separated unique identifiers, canonical single spaces. */
        char *m=cols[3]; unsigned mc=0;
        if (!*m || *m==' ') return 0;
        while (*m) {
            char *tok=m;
            while (*m && *m!=' ') ++m;
            if (*m==' ') { *m++=0; if (!*m || *m==' ') return 0; }
            if (++mc>8 || !oc_member_name_ok(tok) || mcount==128) return 0;
            for (unsigned j=0; j<mcount; ++j) if (oc_equal(seen_members[j],tok)) return 0;
            seen_members[mcount++]=tok;
        }
        OcService *row=&cat->rows[cat->count++];
        row->id=cols[0]; row->label=cols[1]; row->def=cols[2]; row->enable=cols[4]; row->disable=cols[5];
    }
    return cat->count>0 && counted==bytes;
}

int oc_prefs_parse(char *text, const OcCatalog *cat, int active, OcPrefs *out) {
    if (!oc_oc2_decode(text,active,out,0)) return 0;
    if (out->is_oc2 && cat) {
        if (out->svc_count!=cat->count) return 0;
        for (unsigned i=0; i<out->svc_count; ++i) if (!oc_equal(out->svc_ids[i],cat->rows[i].id)) return 0;
    }
    return 1;
}

int oc_append(char *out, unsigned cap, unsigned *at, const char *s) {
    unsigned n=oc_length(s);
    if (*at+n>=cap) return 0;
    for (unsigned i=0; i<n; ++i) out[(*at)++]=s[i];
    out[*at]=0;
    return 1;
}

int oc_prefs_write(const OcCatalog *cat, const OcPrefs *p, char *out, unsigned cap) {
    unsigned at=0;
    if (!cat || !cat->count || cat->count!=p->svc_count) return 0;
    if (!oc_append(out,cap,&at,"OC2\nbase=") || !oc_append(out,cap,&at,p->base) ||
        !oc_append(out,cap,&at,"\ncarplay-autoshow=") || !oc_append(out,cap,&at,p->autoshow) ||
        !oc_append(out,cap,&at,"\nhold-scroll=") || !oc_append(out,cap,&at,p->hold_scroll) ||
        !oc_append(out,cap,&at,"\nmenu-loop=") || !oc_append(out,cap,&at,p->menu_loop) ||
        !oc_append(out,cap,&at,"\nmetadata=") || !oc_append(out,cap,&at,p->metadata) ||
        !oc_append(out,cap,&at,"\nnvram=") || !oc_append(out,cap,&at,p->nvram) ||
        !oc_append(out,cap,&at,"\npackage=") || !oc_append(out,cap,&at,p->package) ||
        !oc_append(out,cap,&at,"\nservice-ids=")) return 0;
    for (unsigned i=0; i<cat->count; ++i) {
        if (i && !oc_append(out,cap,&at,",")) return 0;
        if (!oc_append(out,cap,&at,cat->rows[i].id)) return 0;
    }
    for (unsigned i=0; i<cat->count; ++i) {
        if (!oc_append(out,cap,&at,"\nservice.") || !oc_append(out,cap,&at,cat->rows[i].id) ||
            !oc_append(out,cap,&at,"=") || !oc_append(out,cap,&at,p->svc_vals[i])) return 0;
    }
    if (!oc_append(out,cap,&at,"\nsource-order=") || !oc_append(out,cap,&at,p->source_order) ||
        !oc_append(out,cap,&at,"\ntouch=") || !oc_append(out,cap,&at,p->touch) ||
        !oc_append(out,cap,&at,"\nwarning=") || !oc_append(out,cap,&at,p->warning) ||
        !oc_append(out,cap,&at,"\nwireless=") || !oc_append(out,cap,&at,p->wireless) ||
        !oc_append(out,cap,&at,"\n")) return 0;
    return at<=1023;
}
