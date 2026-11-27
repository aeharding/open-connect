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

int oc_service_id(const char *p) {
    unsigned n=0;
    if (*p<'a'||*p>'z') return 0;
    const char *reserved[]={"touch","warning","base","wireless","uart","ssh","carplay-autoshow"};
    for (unsigned i=0; i<sizeof reserved/sizeof *reserved; ++i) if (oc_equal(p,reserved[i])) return 0;
    while (*p) {
        unsigned c=(unsigned char)*p++;
        if (++n>32||!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-')) return 0;
    }
    return n>0;
}

int oc_service_keys(char *text, char **ids, unsigned *count) {
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

int oc_config(OcBoot *b, char *text, char **f, int active, char svc_digest[65]) {
    unsigned mode, uid, gid;
    f[8]="0";
    if (svc_digest) svc_digest[0]=0;
    if (!oc_prefix(text,"OC2\n")) {
        if (active||!oc_one_line(text)||oc_fields(text,f,5)!=5||!oc_equal(f[0],"-")) return 0;
        return oc_bit(f[1])&&oc_bit(f[2])&&oc_nvram_value(f[3])&&
            oc_metadata_mode(f[4],&mode,&uid,&gid);
    }
    (void)b;
    if (!active) return 0;
    char *ids[16]; unsigned count=0, seen=0, service_seen=0;
    const char *keys[]={"package","touch","warning","nvram","metadata","base","wireless"};
    const unsigned slots[]={0,1,2,3,4,6,7};
    char *previous="", *p=text+4;
    f[5]="1";
    OcHash sh;
    if (svc_digest) oc_hash_init(&sh);
    while (*p) {
        char *key=p, *value=0;
        while (*p && *p!='\n') {
            if ((unsigned char)*p<32||(unsigned char)*p==127) return 0;
            if (*p=='=') { if (value) return 0; *p=0; value=p+1; }
            ++p;
        }
        if (!*p||!value||!*value) return 0;
        *p++=0;
        if (oc_order(key,previous)<=0) return 0;
        previous=key;
        if (oc_equal(key,"carplay-autoshow")) {
            if (!oc_bit(value)) return 0;
            f[8]=value; continue;
        }
        if (oc_equal(key,"service-ids")) {
            if (svc_digest) { oc_hash_add(&sh,value,oc_length(value)); oc_hash_add(&sh,"\n",1); }
            if (!oc_service_keys(value,ids,&count)) return 0;
            seen|=128; continue;
        }
        unsigned found=0;
        for (unsigned i=0; i<sizeof keys/sizeof *keys; ++i) if (oc_equal(key,keys[i])) {
            f[slots[i]]=value; seen|=1u<<i; found=1; break;
        }
        if (found) continue;
        if (!oc_prefix(key,"service.")||!oc_bit(value)) return 0;
        for (unsigned i=0; i<count; ++i) if (oc_equal(key+8,ids[i])) {
            service_seen|=1u<<i; found=1;
            if (svc_digest) { oc_hash_add(&sh,key,oc_length(key)); oc_hash_add(&sh,value,1); }
            if (oc_equal(ids[i],"pandora")) f[5]=value;
            break;
        }
        if (!found) return 0;
    }
    if (svc_digest) oc_hash_finish(&sh,svc_digest);
    return seen==255 && service_seen==((1u<<count)-1) && oc_hex(f[0],64) &&
        (oc_bit(f[1])||oc_equal(f[1],"2")) && oc_bit(f[2]) && oc_nvram_value(f[3]) &&
        oc_metadata_mode(f[4],&mode,&uid,&gid) && oc_bit(f[6]) && oc_bit(f[7]);
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
        unsigned len=0;
        for (char *p=fields[5]; *p; ++p) if (*p<'0'||*p>'9'||++len>20) return 0;
        if (!len) return 0;
    }
    return 1;
}

int oc_nvram(OcBoot *b, char value[16]) {
    long parent=oc_openat(b->root,"sys/class/nvram/nv-config/keys",OC_DIRECTORY,0);
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
