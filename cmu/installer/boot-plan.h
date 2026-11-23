/* SPDX-License-Identifier: AGPL-3.0-or-later
 * OCBP1: a bounded data manifest, sealed only after full maintenance checks.
 * Header: OCBP1|baseline snapshot|backend package
 * Input: key|absolute source path or @/snapshot member|expected SHA-256
 * Sealed row appends ten fixed-width metadata fields. Snapshot hashing, not
 * this metadata manifest, binds the plan to the authoritative current record.
 */
#ifndef OC_BOOT_PLAN_H
#define OC_BOOT_PLAN_H
#include "boot-io.h"

enum { OC_PLAN_ROWS=192, OC_LINE_SIZE=1024, OC_PLAN_LIMIT=131072 };
typedef struct { char bytes[4096]; unsigned at,filled,total; int fd; } OcLines;

static unsigned oc_length(const char *p) { unsigned n=0; while (p[n]) ++n; return n; }
static int oc_equal(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *a==*b) { ++a; ++b; }
    return *a==*b;
}
static int oc_hex(const char *p, unsigned n) {
    unsigned i;
    for (i=0; i<n; ++i) if (!((p[i]>='0'&&p[i]<='9')||(p[i]>='a'&&p[i]<='f'))) return 0;
    return !p[n];
}
static int oc_line(OcLines *r, char output[OC_LINE_SIZE]) {
    unsigned n=0;
    for (;;) {
        if (r->at==r->filled) {
            long got=oc_read(r->fd,r->bytes,sizeof r->bytes);
            if (got==-4) continue;
            if (got<0) return -1;
            if (!got) return n?-1:0; /* A cut final line is never complete. */
            r->at=0; r->filled=(unsigned)got;
        }
        unsigned char c=(unsigned char)r->bytes[r->at++];
        if (++r->total>OC_PLAN_LIMIT) return -1;
        if (c=='\n') { output[n]=0; return n?1:-1; }
        if (c<=32 || c>=127 || n+1>=OC_LINE_SIZE) return -1;
        output[n++]=(char)c;
    }
}
static unsigned oc_fields(char *line, char **fields, unsigned capacity) {
    unsigned count=1;
    fields[0]=line;
    for (char *p=line; *p; ++p) if (*p=='|') {
        if (count==capacity) return 0;
        *p=0; fields[count++]=p+1;
    }
    for (unsigned i=0; i<count; ++i) if (!fields[i][0]) return 0;
    return count;
}
static int oc_key(const char *p) {
    unsigned n=0,part=0;
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
static void oc_put_hex(char *p, oc_u64 value, unsigned width) {
    static const char digits[]="0123456789abcdef";
    while (width) { p[--width]=digits[value&15]; value>>=4; }
}
static oc_u64 oc_get_hex(const char *p, unsigned n) {
    oc_u64 value=0;
    while (n--) { unsigned c=(unsigned char)*p++; value=(value<<4)+(c<='9'?c-'0':c-'a'+10); }
    return value;
}
static unsigned oc_meta_text(char *p, const OcMeta *m) {
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
static int oc_meta_parse(char **fields, OcMeta *m) {
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

static int oc_absent_at(int root, const char *path) {
    char parent[192];
    unsigned slash=0,n=oc_length(path);
    for (unsigned i=0; i<n; ++i) if (path[i]=='/') slash=i;
    long directory=root;
    if (slash) {
        for (unsigned i=0; i<slash; ++i) parent[i]=path[i];
        parent[slash]=0;
        directory=oc_beneath(root,parent,OC_DIRECTORY,0);
        if (directory<0) return 0; /* Missing/inaccessible parent is not absence. */
        path+=slash+1;
    }
    long fd=oc_openat((int)directory,path,OC_READ,0);
    if (fd>=0) (void)oc_close((int)fd);
    if (slash) (void)oc_close((int)directory);
    return fd==-2;
}

/* The command is also a read-only diagnostic for an already sealed plan.
 * Successful metadata checking alone never selects features or writes record.
 */
static int oc_plan_rows(int root, int snapshot, int input, int output, int mode) {
    int sealing=mode==1;
    OcLines reader;
    char line[OC_LINE_SIZE],original[OC_LINE_SIZE],seen[OC_PLAN_ROWS][192];
    char *fields[13],digest[65],meta[131];
    unsigned count=0,n;
    reader.at=reader.filled=reader.total=0; reader.fd=input;
    int status=oc_line(&reader,line);
    if (status!=1) return 0;
    n=oc_fields(line,fields,13);
    if (n!=3 || !oc_equal(fields[0],"OCBP1") || !oc_hex(fields[1],64) || !oc_hex(fields[2],64)) return 0;
    if (sealing && (!oc_write_all(output,"OCBP1|",6) || !oc_write_all(output,fields[1],64) ||
        !oc_write_all(output,"|",1) || !oc_write_all(output,fields[2],64) || !oc_write_all(output,"\n",1))) return 0;
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
        OcMeta current,expected;
        int ok;
        if (sealing) {
            ok=oc_hash_copy((int)fd,-1,33554432,digest,&current)==OC_COPY_OK && oc_equal(digest,fields[2]);
        } else if (mode>=2) {
            /* Recovery keeps every old pin except inode/time; selection keeps
             * those too. Both hash the opened, stable source, including version.ini.
             */
            ok=oc_meta_parse(fields+3,&expected)&&
                oc_hash_copy((int)fd,-1,33554432,digest,&current)==OC_COPY_OK&&oc_equal(digest,fields[2])&&
                (mode==2?oc_meta_resealable(&expected,&current):oc_meta_equal(&expected,&current));
        } else {
            ok=oc_meta_parse(fields+3,&expected) && oc_stat((int)fd,&current)>=0 && oc_meta_equal(&expected,&current);
        }
        if (oc_close((int)fd)<0) ok=0;
        if (!ok) return 0;
        if (sealing) {
            n=oc_meta_text(meta,&current);
            if (!oc_write_all(output,original,length) || !oc_write_all(output,meta,n) || !oc_write_all(output,"\n",1)) return 0;
        }
    }
    return status==0 && count>0;
}
#endif
