/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Only a settled, fully attested snapshot may take this path. Return 95
 * before debit to request the embedded full verifier; never retry after debit.
 */
#ifndef OC_BOOT_POLICY_H
#define OC_BOOT_POLICY_H
#include "boot-system.h"

#define OC_DATA "tmp/mnt/data_persist/open-connect"
#define OC_RAM "tmp/open-connect"
enum { OC_SLOW=95, OC_STOCK=2, OC_REFUSE=1, OC_MEMBERS=128 };
typedef struct { char *name,*digest; } OcMember;
typedef struct { OcMember rows[OC_MEMBERS]; unsigned count; } OcManifest;
typedef struct { char *key,*path,*digest; OcMeta meta; int absent,used; } OcInput;
typedef struct {
    int root,data,ram,lock,snapshot,baseline,package,composed,stage,observer,log;
    char record[1024],next[1024],config[1024],access[320],selector[256],base_config[1024],base_access[320];
    char current_manifest[4096],base_manifest[4096],package_manifest[8192],composed_manifest[4096],composed_digest[65];
    char dependencies[24576],plan_text[OC_PLAN_LIMIT+1],scratch[32768];
    char *record_fields[13],*flags[8],*access_fields[6],*base_flags[8],*base_access_fields[6];
    OcManifest current,base,pkg,composition;
    OcInput inputs[OC_PLAN_ROWS]; unsigned input_count;
    char boot[40],token[34],nonce[33],stage_name[64],observer_name[64],log_name[64],times[1024]; unsigned time_count;
    long owner,group,parent;
    int selected,access_present,base_access_present,debited,input_failure,gated,gate_sent,released,metadata_drift;
} OcBoot;
static OcBoot oc_boot;

static const char *const oc_root_names[]={
    "sm.conf","sm_WCP.conf","board.sh","mmui.so","mmui.xml","uia.so","index.html",
    "system-app.js","settings-app.js","base-app.js","manager.so","device-master.xml",
    "eem.so","device-manager.so","rungetty","sshd","ssh-keygen","framework.js","lvds-service"
};
static const char *const oc_root_paths[]={
    "/jci/sm/sm.conf","/jci/sm/sm_WCP.conf","/jci/scripts/get_board_type.sh",
    "/jci/mmui/svcjcimmui.so","/jci/mmui/mmui_config.xml","/jci/mmui/uia/libjciuiasystem.so",
    "/jci/gui/index.html","/jci/gui/apps/system/js/systemApp.js",
    "/jci/gui/apps/syssettings/js/syssettingsApp.js","/jci/gui/framework/js/BaseApp.js",
    "/jci/lib/libjciuiamgr.so","/etc/devmgr_config_master.xml","/jci/vbs/modules/libjcimod_eem.so",
    "/jci/devicemanager/libdevicemanager.so","/usr/bin/rungetty","/usr/sbin/sshd","/usr/bin/ssh-keygen",
    "/jci/gui/framework/js/GuiFramework.js","/jci/lvds/lvds_service"
};
static const char *const oc_composed_names[]={
    "autostart","uia.so","mmui.so","mmui.xml","system-app.js","index-on.html","index-off.html",
    "sm-normal-on.conf","sm-normal-off.conf","sm-wcp-on.conf","sm-wcp-off.conf"
};

static char *oc_digest(OcManifest *manifest,const char *name) {
    for (unsigned i=0;i<manifest->count;++i) if (oc_equal(manifest->rows[i].name,name)) return manifest->rows[i].digest;
    return 0;
}
static int oc_manifest(char *text,OcManifest *manifest,int dependencies) {
    manifest->count=0;
    while (*text) {
        if (manifest->count==OC_MEMBERS) return 0;
        char *start=text,*name=0;
        unsigned n=0;
        while (*text && *text!='\n') { ++text; ++n; }
        if (!*text || n<67 || start[64]!=' ' || start[65]!=' ') return 0;
        *text++=0; start[64]=0; name=start+66;
        if (!oc_hex(start,64) || !oc_key(name) || (!dependencies && oc_equal(name,"files.sha256"))) return 0;
        if (!dependencies) for (char *p=name;*p;++p) if (*p=='/') return 0;
        if (oc_digest(manifest,name)) return 0;
        manifest->rows[manifest->count].name=name;
        manifest->rows[manifest->count++].digest=start;
    }
    return manifest->count>0;
}
static int oc_members(int folder,OcManifest *manifest) {
    unsigned count=0;
#ifdef OC_HOST
    int copy=dup(folder);
    if (copy<0) return 0;
    DIR *directory=fdopendir(copy);
    if (!directory) { close(copy); return 0; }
    struct dirent *entry;
    while ((entry=readdir(directory))) {
        const char *name=entry->d_name;
        if (oc_equal(name,".")||oc_equal(name,"..")) continue;
        if (!oc_equal(name,"files.sha256") && !oc_digest(manifest,name)) { closedir(directory); return 0; }
        if (++count>OC_MEMBERS+1) { closedir(directory); return 0; }
    }
    if (closedir(directory)<0) return 0;
#else
    unsigned char buffer[4096];
    for (;;) {
        long n=oc_syscall4(217,folder,(long)buffer,sizeof buffer,0);
        if (n==-4) continue;
        if (n<0) return 0;
        if (!n) break;
        unsigned at=0;
        while (at<(unsigned)n) {
            if ((unsigned)n-at<20) return 0;
            unsigned length=buffer[at+16]+((unsigned)buffer[at+17]<<8);
            if (length<20 || length>(unsigned)n-at) return 0;
            char *name=(char *)buffer+at+19;
            unsigned size=length-19,j=0;
            while (j<size && name[j]) ++j;
            if (j==size) return 0;
            if (!oc_equal(name,".")&&!oc_equal(name,"..")) {
                if (!oc_equal(name,"files.sha256")&&!oc_digest(manifest,name)) return 0;
                if (++count>OC_MEMBERS+1) return 0;
            }
            at+=length;
        }
    }

#endif
    return count==manifest->count+1;
}
static int oc_load_manifest(int folder,const char *digest,char *text,unsigned capacity,OcManifest *manifest) {
    return oc_verified_text(folder,"files.sha256",digest,text,capacity) &&
        oc_manifest(text,manifest,0) && oc_members(folder,manifest);
}
static int oc_saved_text(int folder,OcManifest *manifest,const char *name,char *text,unsigned capacity) {
    const char *digest=oc_digest(manifest,name);
    return digest && oc_verified_text(folder,name,digest,text,capacity);
}
static int oc_fields_line(char *text,char **fields,unsigned count) {
    return oc_one_line(text) && oc_fields(text,fields,count)==count;
}
static int oc_bit(const char *p) { return oc_equal(p,"0")||oc_equal(p,"1"); }
static int oc_nvram_value(const char *p) { return oc_equal(p,"absent")||oc_equal(p,"enable")||oc_equal(p,"disable"); }
static int oc_record(OcBoot *b) {
    if (oc_text(b->data,"record",b->record,sizeof b->record,0)<0 || !oc_fields_line(b->record,b->record_fields,13)) return 0;
    char **f=b->record_fields;
    if (!oc_equal(f[0],"OC1")||!oc_hex(f[2],32)||!oc_hex(f[3],64)||!oc_hex(f[4],64)||!oc_hex(f[5],64)) return 0;
    for (unsigned i=6;i<=8;++i) if (!oc_equal(f[i],"-")&&!oc_hex(f[i],64)) return 0;
    if (!oc_equal(f[6],"-")||!oc_equal(f[7],"-")||!oc_equal(f[1],"active")) return 0;
    if (oc_length(f[9])!=1||f[9][0]<'0'||f[9][0]>'3') return 0;
    if ((!oc_equal(f[10],"-")&&!oc_uuid(f[10]))||(!oc_equal(f[11],"-")&&!oc_uuid(f[11]))) return 0;
    return oc_equal(f[12],"-")||oc_equal(f[12],"installed")||oc_equal(f[12],"removed")||oc_equal(f[12],"undone")||oc_equal(f[12],"restart");
}
static int oc_metadata_mode(const char *text,unsigned *mode,unsigned *uid,unsigned *gid) {
    unsigned values[3]={0,0,0},field=0,n=0;
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
/* The packaged catalog owns the admitted service keys; no per-service C map. */
static int oc_order(const char *a,const char *b) {
    while (*a && *a==*b) { ++a; ++b; }
    return (unsigned char)*a-(unsigned char)*b;
}
static int oc_service_id(const char *p) {
    unsigned n=0;
    if (*p<'a'||*p>'z') return 0;
    const char *reserved[]={"touch","warning","base","wireless","uart","ssh"};
    for (unsigned i=0;i<sizeof reserved/sizeof *reserved;++i) if (oc_equal(p,reserved[i])) return 0;
    while (*p) {
        unsigned c=(unsigned char)*p++;
        if (++n>32||!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-')) return 0;
    }
    return n>0;
}
/* Maintenance validates this canonical key set against the catalog. It lives
 * inside the already authenticated config, so selection needs no catalog I/O.
 */
static int oc_service_keys(char *text,char **ids,unsigned *count) {
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
static int oc_config(OcBoot *b,char *text,char **f,int active) {
    unsigned mode,uid,gid;
    if (!oc_prefix(text,"OC2\n")) {
        if (!oc_one_line(text)||oc_fields(text,f,8)!=(active?8u:5u)) return 0;
        if (active?!oc_hex(f[0],64):!oc_equal(f[0],"-")) return 0;
        return oc_bit(f[1])&&oc_bit(f[2])&&oc_nvram_value(f[3])&&
            oc_metadata_mode(f[4],&mode,&uid,&gid)&&
            (!active||(oc_bit(f[5])&&oc_bit(f[6])&&oc_bit(f[7])));
    }
    (void)b;
    if (!active) return 0;
    char *ids[16]; unsigned count=0,seen=0,service_seen=0;
    const char *keys[]={"package","touch","warning","nvram","metadata","base","wireless"};
    const unsigned slots[]={0,1,2,3,4,6,7};
    char *previous="",*p=text+4;
    f[5]="1";
    while (*p) {
        char *key=p,*value=0;
        while (*p && *p!='\n') {
            if ((unsigned char)*p<32||(unsigned char)*p==127) return 0;
            if (*p=='=') { if (value) return 0; *p=0; value=p+1; }
            ++p;
        }
        if (!*p||!value||!*value) return 0;
        *p++=0;
        if (oc_order(key,previous)<=0) return 0;
        previous=key;
        if (oc_equal(key,"service-ids")) {
            if (!oc_service_keys(value,ids,&count)) return 0;
            seen|=128; continue;
        }
        unsigned found=0;
        for (unsigned i=0;i<sizeof keys/sizeof *keys;++i) if (oc_equal(key,keys[i])) {
            f[slots[i]]=value; seen|=1u<<i; found=1; break;
        }
        if (found) continue;
        if (!oc_prefix(key,"service.")||!oc_bit(value)) return 0;
        for (unsigned i=0;i<count;++i) if (oc_equal(key+8,ids[i])) {
            service_seen|=1u<<i; found=1;
            if (oc_equal(ids[i],"pandora")) f[5]=value;
            break;
        }
        if (!found) return 0;
    }
    return seen==255 && service_seen==((1u<<count)-1) && oc_hex(f[0],64)&&
        oc_bit(f[1])&&oc_bit(f[2])&&oc_nvram_value(f[3])&&
        oc_metadata_mode(f[4],&mode,&uid,&gid)&&oc_bit(f[6])&&oc_bit(f[7]);
}
static int oc_input_mode(OcInput *input,const char *text) {
    unsigned mode,uid,gid;
    return !input->absent && oc_metadata_mode(text,&mode,&uid,&gid) &&
        input->meta.mode==(OC_REGULAR|mode) && input->meta.uid==uid && input->meta.gid==gid;
}
static OcInput *oc_find(OcBoot *b,const char *key) {
    for (unsigned i=0;i<b->input_count;++i) if (oc_equal(b->inputs[i].key,key)) return &b->inputs[i];
    return 0;
}
static OcInput *oc_expect(OcBoot *b,const char *key,const char *path,const char *digest) {
    OcInput *row=oc_find(b,key);
    if (!row||row->used||!oc_equal(row->path,path)||!oc_equal(row->digest,digest)) return 0;
    row->used=1;
    return row;
}
static int oc_plan(OcBoot *b) {
    if (!oc_saved_text(b->snapshot,&b->current,"boot.plan",b->plan_text,sizeof b->plan_text)) return 0;
    char *p=b->plan_text,*fields[13];
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
            for (unsigned i=3;i<13;++i) if (!oc_equal(fields[i],"-")) return 0;
            if (!oc_absent_at(parent,path)) return 0;
        } else {
            if (!oc_hex(fields[2],64)||!oc_meta_parse(fields+3,&row->meta)) return 0;
            long fd=oc_beneath(parent,path,OC_READ,0);
            if (fd<0) return 0;
            OcMeta actual;
            int ok=oc_stat((int)fd,&actual)>=0;
            if (oc_close((int)fd)<0) ok=0;
            if (!ok) return 0;
            if (!oc_meta_equal(&row->meta,&actual)) {
                /* Only identical-byte inode/time drift may request resealing.
                 * Keep permission, identity and coverage checks; never activate
                 * from these replacement metadata, even if every hash matches.
                 */
                if (!b->gated||!oc_meta_resealable(&row->meta,&actual)) return 0;
                row->meta=actual; b->metadata_drift=1;
            }
        }
    }
    return rows>1;
}
static int oc_expected_members(OcBoot *b,OcManifest *manifest,const char *key_prefix,const char *path_prefix) {
    char key[192],path[192];
    for (unsigned i=0;i<manifest->count;++i) {
        OcMember *m=&manifest->rows[i];
        if (!oc_join(key,sizeof key,key_prefix,m->name)||!oc_join(path,sizeof path,path_prefix,m->name)||
            !oc_expect(b,key,path,m->digest)) return 0;
    }
    return 1;
}
static int oc_dependency_coverage(OcBoot *b) {
    OcManifest dependencies;
    char name[192],path[192],scope[96],prefix[192];
    if (!oc_saved_text(b->snapshot,&b->current,"dependencies",b->dependencies,sizeof b->dependencies)||
        !oc_manifest(b->dependencies,&dependencies,1)) return 0;
    unsigned expected=sizeof oc_root_names/sizeof *oc_root_names + b->pkg.count+1+b->composition.count+1;
    if (dependencies.count!=expected) return 0;
    for (unsigned i=0;i<sizeof oc_root_names/sizeof *oc_root_names;++i) {
        if (!oc_join(name,sizeof name,"root/",oc_root_names[i])) return 0;
        const char *digest=oc_digest(&dependencies,name);
        if (!digest||!oc_expect(b,name,oc_root_paths[i],digest)) return 0;
    }
    for (unsigned kind=0;kind<2;++kind) {
        OcManifest *m=kind?&b->composition:&b->pkg;
        if (!oc_join(scope,sizeof scope,kind?"composed-":"package-",b->record_fields[3])||
            !oc_join(scope,sizeof scope,scope,"/")||
            !oc_join(prefix,sizeof prefix,kind?"/" OC_DATA "/composed/":"/" OC_DATA "/packages/",b->record_fields[3])||
            !oc_join(prefix,sizeof prefix,prefix,"/")) return 0;
        for (unsigned i=0;i<=m->count;++i) {
            const char *leaf=i==m->count?"files.sha256":m->rows[i].name;
            const char *digest=i==m->count?(kind?b->composed_digest:b->record_fields[3]):m->rows[i].digest;
            if (!oc_join(name,sizeof name,scope,leaf)||!oc_join(path,sizeof path,prefix,leaf)) return 0;
            const char *recorded=oc_digest(&dependencies,name);
            if (!recorded||!oc_equal(recorded,digest)) return 0;
            /* The composed manifest row is looked up before its manifest was parsed. */
            if (kind && i==m->count) {
                OcInput *row=oc_find(b,name);
                if (!row||row->used||!oc_equal(row->path,path)||!oc_equal(row->digest,digest)) return 0;
                row->used=1;
            } else if (!oc_expect(b,name,path,digest)) return 0;
        }
    }
    return 1;
}

static int oc_mounts(OcBoot *b) {
    if (oc_text(b->root,"proc/self/mounts",b->scratch,sizeof b->scratch,1)<0) return 0;
    unsigned root=0,data=0,rootfs=0;
    char *p=b->scratch;
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
        if (oc_equal(f[1],"/")) {
            if (oc_equal(f[0],"rootfs")&&oc_equal(f[2],"rootfs")&&oc_equal(f[3],"rw")&&!root&&!rootfs) ++rootfs;
            else {
                if (!oc_equal(f[0],"/dev/ffx01p1")||!oc_equal(f[2],"relfs")||!oc_equal(f[3],"ro,noatime")) return 0;
                ++root;
            }
        }
        if (oc_equal(f[1],"/tmp/mnt/data_persist")) {
            if (!oc_equal(f[0],"/dev/mmcblk0p2")||!oc_equal(f[2],"relfs")) return 0;
            char options[256];
            if (!oc_join(options,sizeof options,",",f[3])||!oc_join(options,sizeof options,options,",")) return 0;
            int rw=0;
            for (char *q=options;*q;++q) if (oc_prefix(q,",rw,")) ++rw;
            if (rw!=1) return 0;
            ++data;
        }
        /* Reject overlays anywhere inside the two guarded trees. */
        if (oc_equal(f[1],"/" OC_DATA)||oc_prefix(f[1],"/" OC_DATA "/")||
            oc_equal(f[1],"/" OC_RAM)||oc_prefix(f[1],"/" OC_RAM "/")) return 0;
    }
    return root==1 && data==1;
}
static int oc_open_private(int parent,const char *path) {
    long fd=oc_beneath(parent,path,OC_DIRECTORY,0);
    if (fd<0) return -1;
    if (!oc_private((int)fd)) { (void)oc_close((int)fd); return -1; }
    return (int)fd;
}
static int oc_access(char *text,char **fields) {
    if (!oc_one_line(text)) return 0;
    unsigned n=oc_fields(text,fields,6);
    if (n==5) fields[5]="-";
    else if (n!=6) return 0;
    if (!oc_bit(fields[0])||!oc_bit(fields[1])||(!oc_equal(fields[2],"-")&&!oc_hex(fields[2],64))) return 0;
    if (oc_equal(fields[1],"1")&&!oc_hex(fields[2],64)) return 0;
    for (unsigned i=3;i<5;++i) {
        unsigned mode,uid,gid;
        if (!oc_metadata_mode(fields[i],&mode,&uid,&gid)) return 0;
    }
    if (!oc_equal(fields[5],"-")) {
        unsigned n=0;
        for (char *p=fields[5];*p;++p) if (*p<'0'||*p>'9'||++n>20) return 0;
        if (!n) return 0;
    }
    return 1;
}
static int oc_snapshot_coverage(OcBoot *b) {
    char key[192],path[192];
    const char *required[]={"autostart","config","dependencies","selector","sm-normal.conf","sm-wcp.conf","index.html","boot.plan"};
    if (b->current.count!=(b->access_present?11u:8u)) return 0;
    for (unsigned i=0;i<sizeof required/sizeof *required;++i) if (!oc_digest(&b->current,required[i])) return 0;
    for (unsigned i=0;i<b->current.count;++i) {
        OcMember *m=&b->current.rows[i];
        if (oc_equal(m->name,"boot.plan")) continue;
        if (!oc_join(key,sizeof key,"current/",m->name)||!oc_join(path,sizeof path,"@/",m->name)||
            !oc_expect(b,key,path,m->digest)) return 0;
    }
    if (!oc_join(path,sizeof path,"/" OC_DATA "/snapshots/",b->record_fields[4])||!oc_join(path,sizeof path,path,"/")) return 0;
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
    unsigned mode,uid,gid;
    if (!oc_metadata_mode(selector[1],&mode,&uid,&gid)||mode!=0700||uid!=(unsigned)b->owner||gid!=(unsigned)b->group) return 0;
    row=oc_expect(b,"target/boot-select","/usr/bin/open-connect-boot-select",selector[0]);
    if (!row||!oc_input_mode(row,selector[1])) return 0;
    if (oc_digest(&b->base,"selector")) {
        if (!oc_saved_text(b->baseline,&b->base,"selector",b->scratch,sizeof b->scratch)||!oc_equal(b->scratch,"-\n")) return 0;
    }
    return 1;
}

static int oc_decimal(const char *p,oc_u64 *value) {
    oc_u64 n=0;
    if (!*p) return 0;
    while (*p) {
        unsigned digit=(unsigned char)*p++-'0';
        if (digit>9 || n>1844674407370955161ULL || (n==1844674407370955161ULL&&digit>5)) return 0;
        n=n*10+digit;
    }
    *value=n; return 1;
}
static int oc_access_coverage(OcBoot *b) {
    if (!b->access_present) return !b->base_access_present;
    if (!b->base_access_present) return 0;
    char **f=b->access_fields,**base=b->base_access_fields,path[192];
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
        if (!oc_join(path,sizeof path,"/" OC_DATA "/keys/",f[2])||!oc_join(path,sizeof path,path,".cmu")||
            !oc_expect(b,"key/owner",path,f[2])) return 0;
    }
    return 1;
}
static int oc_identity_coverage(OcBoot *b) {
    OcInput *version=oc_find(b,"guard/version.ini");
    if (!version||version->used||!oc_equal(version->path,"/jci/version.ini")||version->absent||
        !oc_verified_text(b->root,"jci/version.ini",version->digest,b->scratch,sizeof b->scratch)) return 0;
    version->used=1;
    const char *values[]={"JCI_SW_VER=\"MAZ_CMU-150_74.00.324\"","JCI_SW_VER_PATCH=\"A\"","JCI_SW_FLAVOR=\"cmu150_NA\""};
    unsigned found[3]={0,0,0}; char *p=b->scratch;
    while (*p) {
        char *line=p;
        while (*p && *p!='\n') ++p;
        if (!*p) return 0;
        *p++=0;
        for (unsigned i=0;i<3;++i) if (oc_equal(line,values[i])) ++found[i];
    }
    if (found[0]!=1||found[1]!=1||found[2]!=1) return 0;
    if (oc_equal(b->flags[6],"1")) {
        if (!oc_expect(b,"base/settings.txt","/config/common/log/settings.txt","8c95ceaf213af1086e913fd78b69c9b00869c848375c3b40de3c36166d5d3ea0")||
            !oc_expect(b,"base/libjcicommon.so","/jci/lib/libjcicommon.so","637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d")||
            !oc_expect(b,"base/log-defaults.js","/jci/gui/common/js/logDefaults.js","83f5a71617f34427bb903c90ac5df53ed4e0e6437cca8a8bdb509909a324ba3a")) return 0;
    }
    for (unsigned i=0;i<b->input_count;++i) if (!b->inputs[i].used) return 0;
    return 1;
}

static void oc_stamp(OcBoot *b,const char *phase) {
    char tick[96],line[160];
    if (b->time_count>=12 || oc_text(b->root,"proc/uptime",tick,sizeof tick,1)<0) return;
    unsigned n=0;
    while (tick[n] && tick[n]!=' ') {
        if (!((tick[n]>='0'&&tick[n]<='9')||tick[n]=='.')) return;
        ++n;
    }
    if (!n||tick[n]!=' ') return;
    tick[n]=0;
    if (!oc_join(line,sizeof line,phase,"|")||!oc_join(line,sizeof line,line,tick)||
        !oc_join(line,sizeof line,line,"\n")||!oc_join(b->times,sizeof b->times,b->times,line)) return;
    ++b->time_count;
}
/* One waitable process retains the lock and decision across the OEM interval.
 * A frame grants only permission to continue Mazda startup, never selection.
 */
static int oc_gate(OcBoot *b,int release) {
    if (!b->gated||b->gate_sent) return 1;
    b->gate_sent=1;
    if (b->parent<=1||oc_parent()!=b->parent) return 0;
    char frame=release?'G':'J';
    int ok=oc_write_all(1,&frame,1);
    if (oc_close(1)<0) ok=0;
    if (ok&&release) { b->released=1; oc_stamp(b,"gate_released"); oc_cut("gate_released"); }
    return ok;
}
static int oc_new_text(int folder,const char *name,const char *text,unsigned mode) {
    long fd=oc_openat(folder,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,mode);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,text,oc_length(text)) && oc_mode((int)fd,mode)>=0;
    if (oc_close((int)fd)<0) ok=0;
    return ok;
}
static int oc_copy_input(OcBoot *b,const char *key,int output,const char *name,unsigned mode) {
    OcInput *row=oc_find(b,key);
    if (!row||row->absent) { b->input_failure=1; return 0; }
    int parent=b->root;
    const char *path=row->path;
    if (oc_prefix(path,"@/")) { parent=b->snapshot; path+=2; }
    else ++path;
    long input=oc_beneath(parent,path,OC_READ,0);
    if (input<0) { b->input_failure=1; return 0; }
    long target=-1;
    if (output>=0) {
        target=oc_openat(output,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,mode);
        if (target<0) { (void)oc_close((int)input); return 0; }
    }
    char digest[65]; OcMeta actual;
    int copied=oc_hash_copy((int)input,(int)target,33554432,digest,&actual);
    int ok=copied==OC_COPY_OK;
    if (copied==OC_COPY_SOURCE) b->input_failure=1;
    if (ok && (!oc_equal(digest,row->digest)||!oc_meta_equal(&row->meta,&actual))) {
        b->input_failure=1; ok=0;
    }
    if (ok && target>=0) ok=oc_mode((int)target,mode)>=0;
    if (oc_close((int)input)<0) { b->input_failure=1; ok=0; }
    if (target>=0 && oc_close((int)target)<0) ok=0;
    return ok;
}
/* Advisory only: a matching request forces the verified shell before Mazda's
 * profile/NVRAM jobs. Stale IDs cannot authorize anything and are ignored.
 */
static int oc_reseal_hint(OcBoot *b) {
    long fd=oc_openat(b->data,"reseal",OC_READ,0);
    if (fd==-2) return 0;
    if (fd<0) return -1;
    OcMeta before,after; char text[66];
    int ok=oc_stat((int)fd,&before)>=0&&before.mode==(OC_REGULAR|0600)&&before.size==65&&
        before.uid==(unsigned)b->owner&&before.gid==(unsigned)b->group;
    if (ok) ok=oc_text_fd((int)fd,text,sizeof text)==65&&oc_one_line(text)&&oc_hex(text,64)&&
        oc_stat((int)fd,&after)>=0&&oc_meta_equal(&before,&after);
    if (oc_close((int)fd)<0) ok=0;
    return ok?oc_equal(text,b->record_fields[5]):-1;
}
static int oc_request_reseal(OcBoot *b) {
    /* Hash ALL covered inputs. An unrelated corrupt member must not turn a
     * recoverable inode change into repeated expensive shell verification.
     */
    for (unsigned i=0;i<b->input_count;++i) {
        OcInput *row=&b->inputs[i];
        if (!row->absent&&!oc_copy_input(b,row->key,-1,0,0)) return 0;
    }
    if (oc_reseal_hint(b)<0||!oc_random(b->root,b->nonce)) return 0;
    char name[64],text[66];
    if (!oc_join(name,sizeof name,".reseal-",b->nonce)||!oc_join(text,sizeof text,b->record_fields[5],"\n")) return 0;
    long fd=oc_openat(b->data,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,text,65)&&oc_mode((int)fd,0600)>=0&&oc_sync((int)fd)>=0;
    oc_cut("reseal_synced");
    if (oc_close((int)fd)<0) ok=0;
    if (ok) ok=oc_rename(b->data,name,"reseal")>=0&&oc_sync(b->data)>=0;
    if (!ok) (void)oc_unlink(b->data,name);
    oc_cut("reseal_published");
    return ok;
}
static int oc_package_copy(OcBoot *b,const char *name,int output,const char *destination,unsigned mode) {
    char key[192];
    return oc_join(key,sizeof key,"package-",b->record_fields[3]) && oc_join(key,sizeof key,key,"/") &&
        oc_join(key,sizeof key,key,name) && oc_copy_input(b,key,output,destination,mode);
}
static int oc_composed_copy(OcBoot *b,const char *name,int output,unsigned mode) {
    char key[192];
    return oc_join(key,sizeof key,"composed-",b->record_fields[3]) && oc_join(key,sizeof key,key,"/") &&
        oc_join(key,sizeof key,key,name) && oc_copy_input(b,key,output,name,mode);
}
static int oc_composed_link(OcBoot *b,const char *name) {
    char key[192],target[192];
    /* The private source stays immutable across Set and package upgrades.
     * Hash the opened source exactly as for RAM copies before publishing a link.
     * Both staging and final feature directories have the same parent depth.
     */
    return oc_join(key,sizeof key,"composed-",b->record_fields[3]) &&
        oc_join(key,sizeof key,key,"/") && oc_join(key,sizeof key,key,name) &&
        oc_copy_input(b,key,-1,0,0) &&
        oc_join(target,sizeof target,"../../mnt/data_persist/open-connect/composed/",b->record_fields[3]) &&
        oc_join(target,sizeof target,target,"/") && oc_join(target,sizeof target,target,name) &&
        oc_symlink(target,b->stage,name)>=0;
}
static int oc_nvram(OcBoot *b,char value[16]) {
    /* These class parents are kernel-owned sysfs links, unlike durable paths.
     * Open the keys directory first so inaccessible parents cannot mean absent.
     */
    long parent=oc_openat(b->root,"sys/class/nvram/nv-config/keys",OC_DIRECTORY,0);
    if (parent<0) return 0;
    long fd=oc_openat((int)parent,"lvds_speed_restriction",OC_READ,0);
    int ok=0;
    if (fd==-2) ok=oc_join(value,16,"","absent");
    else if (fd>=0) {
        /* This v74 driver returns a terminal NUL, unlike ordinary proc text.
         * Keep that binary convention local; immutable text still rejects NUL.
         */
        OcMeta metadata;
        unsigned n=0;
        /* oc_openat is nonblocking and refuses a symlink at the leaf. */
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
static int oc_budget_policy(OcBoot *b) {
    char acc[8],nvram[16];
    if (oc_text(b->root,"sys/class/gpio/ACC_Sense/value",acc,sizeof acc,1)<0||
        !oc_one_line(acc)||!oc_bit(acc)||!oc_nvram(b,nvram)||!oc_equal(nvram,b->flags[3])) return 0;
    unsigned budget=(unsigned)(b->record_fields[9][0]-'0');
    if (!oc_equal(b->record_fields[10],"-") && !oc_equal(b->record_fields[10],b->boot) && oc_equal(acc,"1")) budget=3;
    b->selected=budget>0;
    const char *wanted=b->base_flags[3];
    if (b->selected && oc_equal(b->flags[1],"1")) wanted="disable";
    /* NVRAM writes need the full shell transaction and firmware adapter. */
    if (!oc_equal(wanted,nvram)) return 0;
    b->record_fields[9]=budget?(budget==3?"2":budget==2?"1":"0"):"0";
    b->record_fields[10]="-";
    b->record_fields[11]=b->boot;
    return 1;
}
static int oc_token(OcBoot *b) {
    if (oc_absent_at(b->ram,"token")) {
        if (!oc_random(b->root,b->token)) return 0;
        b->token[32]='\n'; b->token[33]=0;
        if (!oc_new_text(b->ram,"token",b->token,0600)) return 0;
    } else if (oc_text(b->ram,"token",b->token,sizeof b->token,0)!=33) return 0;
    if (b->token[32]!='\n') return 0;
    b->token[32]=0;
    return oc_hex(b->token,32);
}
static int oc_stage(OcBoot *b) {
    if (!oc_random(b->root,b->nonce)||!oc_join(b->observer_name,sizeof b->observer_name,".ignition-",b->nonce)||
        oc_mkdir(b->ram,b->observer_name,0700)<0) return 0;
    b->observer=oc_open_private(b->ram,b->observer_name);
    if (b->observer<0 || !oc_package_copy(b,"ignition.sh",b->observer,"ignition.sh",0600)||
        !oc_package_copy(b,"state.sh",b->observer,"state.sh",0600)||!oc_package_copy(b,"flush",b->observer,"flush",0700)) return 0;
    if (!b->selected) return 1;
    if (!oc_token(b)||!oc_join(b->stage_name,sizeof b->stage_name,".feature-",b->nonce)||oc_mkdir(b->ram,b->stage_name,0700)<0) return 0;
    b->stage=oc_open_private(b->ram,b->stage_name);
    if (b->stage<0||!oc_copy_input(b,"current/sm-normal.conf",b->stage,"sm.conf",0600)||
        !oc_copy_input(b,"current/sm-wcp.conf",b->stage,"sm_WCP.conf",0600)) return 0;
    if (oc_equal(b->flags[2],"1")) {
        if (!oc_composed_link(b,"uia.so")||!oc_composed_link(b,"system-app.js")||
            !oc_composed_copy(b,"mmui.so",b->stage,0600)||!oc_composed_copy(b,"mmui.xml",b->stage,0600)) return 0;
    }
    if (oc_equal(b->flags[6],"1") && oc_equal(b->flags[7],"1") &&
        !oc_package_copy(b,"defer-gap2.sh",b->stage,"defer-gap2.sh",0600)) return 0;
    const char *ui[]={"runtime.js","dialog.js","settings.js"};
    for (unsigned i=0;i<3;++i) if (!oc_package_copy(b,ui[i],b->stage,ui[i],0600)) return 0;
    if (!oc_package_copy(b,"service.sh",b->stage,"service.sh",0600)) return 0;
    if (oc_equal(b->flags[7],"1")) {
        if (!oc_package_copy(b,"wireless.sh",b->stage,"wireless.sh",0600)||
            !oc_package_copy(b,"wireless-device.awk",b->stage,"wireless-device.awk",0600)||
            !oc_join(b->scratch,sizeof b->scratch,b->boot,"\n")||
            !oc_new_text(b->stage,"boot-id",b->scratch,0600)||!oc_new_text(b->stage,"wireless-applied","0\n",0600)) return 0;
    }
    char version[64];
    if (!oc_saved_text(b->package,&b->pkg,"VERSION",version,sizeof version)||!oc_one_line(version)) { b->input_failure=1; return 0; }
    for (const char *p=version;*p;++p) if (!((*p>='0'&&*p<='9')||(*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||*p=='.'||*p=='-')) return 0;
    if (!oc_saved_text(b->snapshot,&b->current,"index.html",b->scratch,sizeof b->scratch)) { b->input_failure=1; return 0; }
    char output[32768]; unsigned used=0,slots[3]={0,0,0};
    const char *needles[]={"@TOKEN@","@VERSION@","@NOTICE@"};
    const char *values[]={b->token,version,b->record_fields[12]};
    for (const char *p=b->scratch;*p;) {
        unsigned i=0;
        while (i<3 && !oc_prefix(p,needles[i])) ++i;
        if (i<3) {
            unsigned n=oc_length(values[i]);
            if (used+n>=sizeof output) return 0;
            for (unsigned j=0;j<n;++j) output[used++]=values[i][j];
            ++slots[i]; p+=oc_length(needles[i]);
        } else { if (used+1>=sizeof output) return 0; output[used++]=*p++; }
    }
    output[used]=0;
    if (slots[0]!=1||slots[1]!=1||slots[2]!=1) { b->input_failure=1; return 0; }
    if (!oc_new_text(b->stage,"index.html",output,0600)) return 0;
    return 1;
}
static int oc_record_commit(OcBoot *b) {
    if (!oc_random(b->root,b->nonce)) return 0;
    b->record_fields[2]=b->nonce; b->record_fields[8]="-";
    b->next[0]=0;
    for (unsigned i=0;i<13;++i) if (!oc_join(b->next,sizeof b->next,b->next,b->record_fields[i])||
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
    if (oc_text(b->data,"record",b->scratch,sizeof b->scratch,0)<0||!oc_equal(b->scratch,b->next)) return 0;
    return 1;
}



static int oc_log_stage(OcBoot *b) {
    if (!b->selected||!oc_equal(b->flags[6],"1")) return 1;
    const char *paths[]={"tmp/common","tmp/common/log"};
    for (unsigned i=0;i<2;++i) {
        long fd=oc_beneath(b->root,paths[i],OC_DIRECTORY,0);
        if (fd==-2) {
            if (oc_mkdir(b->root,paths[i],0755)<0) return 0;
            fd=oc_beneath(b->root,paths[i],OC_DIRECTORY,0);
        }
        if (fd<0) return 0;
        OcMeta meta;
        int ok=oc_stat((int)fd,&meta)>=0 && meta.uid==(unsigned)b->owner && !(meta.mode&0022);
        if (i==1) b->log=(int)fd;
        else if (oc_close((int)fd)<0) ok=0;
        if (!ok) return 0;
    }
    return oc_absent_at(b->log,"settings.txt") && oc_join(b->log_name,sizeof b->log_name,".open-connect-log-",b->nonce) &&
        oc_new_text(b->log,b->log_name,"COMMON_LOG_LEVEL=Warn\n",0644);
}
static int oc_publish(OcBoot *b) {
    if (b->gated&&oc_parent()!=b->parent) return 0;
    if (!oc_absent_at(b->ram,"selected")||!oc_absent_at(b->ram,"feature")||!oc_absent_at(b->ram,"ignition")) return 0;
    char selected[66];
    if (!oc_join(selected,sizeof selected,b->record_fields[5],"\n")||
        !oc_new_text(b->ram,".native-selected",selected,0600)) return 0;
    if (b->access_present && !oc_new_text(b->ram,"access-selected",selected,0600)) return 0;
    /* Only RAM publication syscalls remain after blocking cancellation. */
    oc_cut("before_publication");
    if (oc_block()<0) return 0;
    oc_cut("publication");
    if (oc_rename(b->ram,b->observer_name,"ignition")<0) return 0;
    if (!b->selected) return 1;
    if (oc_rename(b->ram,b->stage_name,"feature")<0) return 0;
    if (b->log>=0 && oc_link(b->log,b->log_name,b->log,"settings.txt")<0) return 0;
    if (oc_link(b->ram,".native-selected",b->ram,"selected")<0) {
        /* The staged inode remains as independent ownership evidence. */
        if (b->log>=0) {
            long fd=oc_openat(b->log,"settings.txt",OC_READ,0),held=oc_openat(b->log,b->log_name,OC_READ,0);
            OcMeta a,c;
            if (fd>=0&&held>=0&&oc_stat((int)fd,&a)>=0&&oc_stat((int)held,&c)>=0&&a.device==c.device&&a.inode==c.inode)
                (void)oc_unlink(b->log,"settings.txt");
            if (fd>=0) (void)oc_close((int)fd);
            if (held>=0) (void)oc_close((int)held);
        }
        return 0;
    }
    (void)oc_unlink(b->ram,".native-selected");
    if (b->log>=0) (void)oc_unlink(b->log,b->log_name);
    return 1;
}
static int oc_base_read_ahead(OcBoot *b) {
    /* The kernel queue is volatile and shared by ffx01's partitions. Tune only
     * after a durable, successful Base selection. Failure is diagnostic: it
     * must never undo a published selection or initiate late shell recovery.
     */
    if (!b->selected||!oc_equal(b->flags[6],"1")) return 1;
    char value[16];
    if (oc_text(b->root,"sys/devices/virtual/block/ffx01/dev",value,sizeof value,0)<0||
        !oc_equal(value,"253:16\n")) return 0;
    long queue=oc_beneath(b->root,"sys/devices/virtual/block/ffx01/queue",OC_DIRECTORY,0);
    if (queue<0) return 0;
    int ok=oc_text((int)queue,"read_ahead_kb",value,sizeof value,0)>=0;
    if (ok && oc_equal(value,"128\n")) {
        long fd=oc_openat((int)queue,"read_ahead_kb",OC_WRITE,0);
        OcMeta meta;
        ok=fd>=0 && oc_stat((int)fd,&meta)>=0 && meta.mode==(OC_REGULAR|0644) &&
            meta.uid==(unsigned)b->owner && meta.gid==(unsigned)b->group && oc_write_all((int)fd,"4\n",2);
        if (fd>=0 && oc_close((int)fd)<0) ok=0;
        if (ok) ok=oc_text((int)queue,"read_ahead_kb",value,sizeof value,0)>=0;
    }
    ok=ok && oc_equal(value,"4\n");
    if (oc_close((int)queue)<0) ok=0;
    return ok;
}
static int oc_policy_load(OcBoot *b) {
    char path[192];
    if (!oc_join(path,sizeof path,"snapshots/",b->record_fields[5])) return 0;
    b->snapshot=oc_open_private(b->data,path);
    if (!oc_join(path,sizeof path,"snapshots/",b->record_fields[4])) return 0;
    b->baseline=oc_open_private(b->data,path);
    if (b->snapshot<0||b->baseline<0||
        !oc_load_manifest(b->snapshot,b->record_fields[5],b->current_manifest,sizeof b->current_manifest,&b->current)||
        !oc_load_manifest(b->baseline,b->record_fields[4],b->base_manifest,sizeof b->base_manifest,&b->base)||
        !oc_saved_text(b->snapshot,&b->current,"config",b->config,sizeof b->config)||
        !oc_config(b,b->config,b->flags,1)||!oc_equal(b->flags[0],b->record_fields[3])||
        !oc_saved_text(b->baseline,&b->base,"config",b->base_config,sizeof b->base_config)||
        !oc_config(b,b->base_config,b->base_flags,0)) return 0;
    return 1;
}
static int oc_load(OcBoot *b) {
    char path[192];
    if (!oc_join(path,sizeof path,"packages/",b->record_fields[3])) return 0;
    b->package=oc_open_private(b->data,path);
    if (!oc_join(path,sizeof path,"composed/",b->record_fields[3])) return 0;
    b->composed=oc_open_private(b->data,path);
    if (b->package<0||b->composed<0||
        !oc_load_manifest(b->package,b->record_fields[3],b->package_manifest,sizeof b->package_manifest,&b->pkg)||b->pkg.count>64) return 0;
    const char *mandatory[]={"boot-select","boot.sh","state.sh","transaction.sh","firmware.sh","access.sh","service.sh",
        "ignition.sh","flush","api","runtime.js","dialog.js","settings.js","VERSION","INSTANCE"};
    for (unsigned i=0;i<sizeof mandatory/sizeof *mandatory;++i) if (!oc_digest(&b->pkg,mandatory[i])) return 0;
    if (oc_prefix(b->config,"OC2\n") && (!oc_digest(&b->pkg,"preferences.awk")||
        !oc_digest(&b->pkg,"services.tsv")||!oc_digest(&b->pkg,"sm-profile.awk"))) return 0;
    b->access_present=oc_digest(&b->current,"access")!=0;
    b->base_access_present=oc_digest(&b->base,"access")!=0;
    if (b->access_present && (!oc_saved_text(b->snapshot,&b->current,"access",b->access,sizeof b->access)||!oc_access(b->access,b->access_fields))) return 0;
    if (b->base_access_present && (!oc_saved_text(b->baseline,&b->base,"access",b->base_access,sizeof b->base_access)||!oc_access(b->base_access,b->base_access_fields))) return 0;
    if (!oc_plan(b)||!oc_join(path,sizeof path,"composed-",b->record_fields[3])||!oc_join(path,sizeof path,path,"/files.sha256")) return 0;
    OcInput *composition=oc_find(b,path);
    if (!composition||!oc_hex(composition->digest,64)||!oc_join(b->composed_digest,sizeof b->composed_digest,"",composition->digest)||
        !oc_load_manifest(b->composed,b->composed_digest,b->composed_manifest,sizeof b->composed_manifest,&b->composition)||
        b->composition.count!=sizeof oc_composed_names/sizeof *oc_composed_names) return 0;
    for (unsigned i=0;i<sizeof oc_composed_names/sizeof *oc_composed_names;++i) if (!oc_digest(&b->composition,oc_composed_names[i])) return 0;
    return oc_dependency_coverage(b)&&oc_snapshot_coverage(b)&&oc_access_coverage(b)&&oc_identity_coverage(b);
}
static int oc_select(OcBoot *b,int root) {
    b->root=root; b->data=b->ram=b->lock=b->snapshot=b->baseline=b->package=b->composed=b->stage=b->observer=b->log=-1;
    b->owner=oc_owner(); b->group=oc_group();
    b->parent=oc_parent();
    if (b->gated&&(b->parent<=1||oc_watch_parent()<0||oc_parent()!=b->parent)) return OC_REFUSE;
#ifndef OC_HOST
    if (b->owner!=0||b->group!=0) return OC_REFUSE;
#endif
    /* The autostart parent stays on CPU0. Only its overlapping worker moves. */
    if (b->gated&&oc_worker_cpu1()<0) return OC_SLOW;
    b->data=oc_open_private(root,OC_DATA);
    if (b->data<0) return OC_SLOW;
    long ram=oc_beneath(root,OC_RAM,OC_DIRECTORY,0);
    if (ram==-2) {
        if (oc_mkdir(root,OC_RAM,0700)<0) return OC_REFUSE;
        ram=oc_beneath(root,OC_RAM,OC_DIRECTORY,0);
    }
    b->ram=(int)ram;
    if (b->ram<0||!oc_private(b->ram)) return OC_REFUSE;
    oc_stamp(b,"hook_entry");
    if (b->gated) oc_stamp(b,"worker_cpu1");
    b->lock=(int)oc_openat(b->ram,"lock",OC_RW|OC_CREATE,0600);
    OcMeta lock_meta,record_meta;
    if (b->lock<0||oc_stat(b->lock,&lock_meta)<0||lock_meta.mode!=(OC_REGULAR|0600)||
        lock_meta.uid!=(unsigned)b->owner||lock_meta.gid!=(unsigned)b->group||oc_lock(b->lock)<0) return OC_REFUSE;
    long record=oc_openat(b->data,"record",OC_READ,0);
    if (record<0) return OC_SLOW;
    int ok=oc_stat((int)record,&record_meta)>=0&&record_meta.mode==(OC_REGULAR|0600)&&
        record_meta.uid==(unsigned)b->owner&&record_meta.gid==(unsigned)b->group;
    if (oc_close((int)record)<0) ok=0;
    if (!ok||!oc_record(b)) return OC_SLOW;
    if (oc_text(root,"proc/sys/kernel/random/boot_id",b->boot,sizeof b->boot,1)<0||!oc_one_line(b->boot)||!oc_uuid(b->boot)) return OC_SLOW;
    if (oc_equal(b->record_fields[11],b->boot)||!oc_absent_at(b->ram,"selected")||
        !oc_absent_at(b->ram,"feature")||!oc_absent_at(b->ram,"ignition")||!oc_absent_at(b->ram,"access-selected")||
        !oc_absent_at(b->ram,".native-selected")) return OC_REFUSE;
    if (!oc_mounts(b)||!oc_policy_load(b)) return OC_SLOW;
    if (b->gated) {
        int hint=oc_reseal_hint(b);
        if (hint<0) return OC_REFUSE;
        if (hint) return OC_SLOW;
    }
    if (!oc_budget_policy(b)) return OC_SLOW;
    if (b->gated) {
        oc_stamp(b,"policy_checked");
        if (!oc_gate(b,1)) return OC_REFUSE;
    }
    if (!oc_load(b)) return OC_SLOW;
    if (b->metadata_drift) {
        (void)oc_request_reseal(b);
        return OC_SLOW;
    }
    oc_stamp(b,"inputs_checked");
    if (!oc_stage(b)) return b->input_failure?OC_SLOW:OC_REFUSE;
    if (!oc_log_stage(b)) return OC_REFUSE;
    oc_stamp(b,"feature_copied");
    if (b->gated&&oc_parent()!=b->parent) return OC_REFUSE;
    if (!oc_record_commit(b)) return OC_REFUSE;
    if (!oc_publish(b)) return OC_REFUSE;
    if (!oc_base_read_ahead(b)) oc_stamp(b,"base_read_ahead_unavailable");
    oc_stamp(b,"selector_exit");
    (void)oc_new_text(b->ram,"startup-times",b->times,0600);
    return b->selected?0:OC_STOCK;
}
static int oc_selection(int root,int gated) {
    oc_boot.gated=gated;
    int result=oc_select(&oc_boot,root);
    if (gated&&!oc_boot.gate_sent&&!oc_gate(&oc_boot,0)) result=OC_REFUSE;
    if (oc_boot.released&&result==OC_SLOW) {
        /* No shell/NVRAM recovery after release. Verified byte-identical
         * metadata drift requests full verification before the NEXT gate.
         */
        (void)oc_write_all(2,"late_verification_refused\n",26);
        result=OC_REFUSE;
    }
    int handles[]={oc_boot.log,oc_boot.observer,oc_boot.stage,oc_boot.composed,oc_boot.package,
        oc_boot.baseline,oc_boot.snapshot,oc_boot.lock,oc_boot.ram,oc_boot.data};
    for (unsigned i=0;i<sizeof handles/sizeof *handles;++i) if (handles[i]>=0) (void)oc_close(handles[i]);
    return result;
}
#endif
