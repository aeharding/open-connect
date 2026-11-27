/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Bounded string, hex, key, and canonical files.sha256 manifest verification.
 */
#include "oc-core.h"

unsigned oc_length(const char *p) { unsigned n=0; while (p[n]) ++n; return n; }

int oc_equal(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *a==*b) { ++a; ++b; }
    return *a==*b;
}

int oc_prefix(const char *p, const char *prefix) {
    while (*prefix) if (*p++!=*prefix++) return 0;
    return 1;
}

int oc_hex(const char *p, unsigned n) {
    for (unsigned i=0; i<n; ++i)
        if (!((p[i]>='0'&&p[i]<='9')||(p[i]>='a'&&p[i]<='f'))) return 0;
    return !p[n];
}

int oc_key(const char *p) {
    unsigned n=0, part=0;
    const char *start=p;
    while (*p) {
        char c=*p++;
        if (++n>=192) return 0;
        if (c=='/') {
            if (!part || (part==1&&start[0]=='.') || (part==2&&start[0]=='.'&&start[1]=='.')) return 0;
            start=p; part=0;
        } else {
            if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='_'||c=='-')) return 0;
            ++part;
        }
    }
    return part && !(part==1&&start[0]=='.') && !(part==2&&start[0]=='.'&&start[1]=='.');
}

int oc_one_line(char *p) {
    unsigned n=oc_length(p);
    if (!n || p[n-1]!='\n') return 0;
    p[n-1]=0;
    for (unsigned i=0; i<n-1; ++i) if ((unsigned char)p[i]<32 || (unsigned char)p[i]>=127) return 0;
    return 1;
}

unsigned oc_fields(char *line, char **fields, unsigned capacity) {
    unsigned count=1;
    fields[0]=line;
    for (char *p=line; *p; ++p) if (*p=='|') {
        if (count==capacity) return 0;
        *p=0; fields[count++]=p+1;
    }
    for (unsigned i=0; i<count; ++i) if (!fields[i][0]) return 0;
    return count;
}

int oc_fields_line(char *text, char **fields, unsigned count) {
    return oc_one_line(text) && oc_fields(text,fields,count)==count;
}

int oc_join(char *out, unsigned capacity, const char *a, const char *b) {
    unsigned n=oc_length(a), m=oc_length(b);
    if (n+m+1>capacity) return 0;
    for (unsigned i=0; i<n; ++i) out[i]=a[i];
    for (unsigned i=0; i<=m; ++i) out[n+i]=b[i];
    return 1;
}

int oc_uuid(const char *p) {
    if (oc_length(p)!=36) return 0;
    for (unsigned i=0; i<36; ++i) {
        if (i==8||i==13||i==18||i==23) { if (p[i]!='-') return 0; }
        else if (!((p[i]>='0'&&p[i]<='9')||(p[i]>='a'&&p[i]<='f'))) return 0;
    }
    return 1;
}

int oc_decimal(const char *p, oc_u64 *value) {
    oc_u64 n=0;
    if (!*p) return 0;
    while (*p) {
        unsigned digit=(unsigned char)*p++-'0';
        if (digit>9 || n>1844674407370955161ULL || (n==1844674407370955161ULL&&digit>5)) return 0;
        n=n*10+digit;
    }
    *value=n; return 1;
}

void oc_put_hex(char *p, oc_u64 value, unsigned width) {
    static const char digits[]="0123456789abcdef";
    while (width) { p[--width]=digits[value&15]; value>>=4; }
}

oc_u64 oc_get_hex(const char *p, unsigned n) {
    oc_u64 value=0;
    while (n--) { unsigned c=(unsigned char)*p++; value=(value<<4)+(c<='9'?c-'0':c-'a'+10); }
    return value;
}

char *oc_digest(OcManifest *manifest, const char *name) {
    for (unsigned i=0; i<manifest->count; ++i) if (oc_equal(manifest->rows[i].name,name)) return manifest->rows[i].digest;
    return 0;
}

int oc_manifest(char *text, OcManifest *manifest, int dependencies) {
    manifest->count=0;
    while (*text) {
        if (manifest->count==OC_MEMBERS) return 0;
        char *start=text, *name=0;
        unsigned n=0;
        while (*text && *text!='\n') { ++text; ++n; }
        if (!*text || n<67 || start[64]!=' ' || start[65]!=' ') return 0;
        *text++=0; start[64]=0; name=start+66;
        if (!oc_hex(start,64) || !oc_key(name) || (!dependencies && oc_equal(name,"files.sha256"))) return 0;
        if (!dependencies) for (char *p=name; *p; ++p) if (*p=='/') return 0;
        if (oc_digest(manifest,name)) return 0;
        manifest->rows[manifest->count].name=name;
        manifest->rows[manifest->count++].digest=start;
    }
    return manifest->count>0;
}

typedef struct { OcManifest *manifest; int expect_manifest; unsigned count; } OcMembersCtx;
static int oc_members_cb(const char *name, void *raw) {
    OcMembersCtx *c=raw;
    if ((c->expect_manifest!=1 || !oc_equal(name,"files.sha256")) && !oc_digest(c->manifest,name)) return -1;
    if (++c->count>OC_MEMBERS+1) return -1;
    return 1;
}

int oc_members(int folder, OcManifest *manifest, int expect_manifest) {
    OcMembersCtx ctx={manifest, expect_manifest, 0};
    if (!oc_dir_iter(folder, oc_members_cb, &ctx)) return 0;
    return expect_manifest==2 ? 1 : ctx.count==manifest->count+(expect_manifest?1u:0u);
}

int oc_load_manifest(int folder, const char *digest, char *text, unsigned capacity, OcManifest *manifest) {
    return oc_verified_text(folder,"files.sha256",digest,text,capacity) &&
        oc_manifest(text,manifest,0) && oc_members(folder,manifest,1);
}

int oc_saved_text(int folder, OcManifest *manifest, const char *name, char *text, unsigned capacity) {
    const char *digest=oc_digest(manifest,name);
    return digest && oc_verified_text(folder,name,digest,text,capacity);
}
