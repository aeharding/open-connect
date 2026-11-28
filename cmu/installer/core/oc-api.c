/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Lean native interactive API handlers for Settings and USB maintenance.
 * Links only oc-hash, oc-io, oc-manifest, oc-record, oc-config, oc-guard;
 * invokes verified persistent boot-select via fork+execve (zero C duplication).
 */
#include "oc-core.h"

#ifdef OC_HOST
#include <stdlib.h>
extern char **environ;
#endif

static struct {
    char json[16384];
    char cat_buf[16384];
    char mf_buf[8192];
    char hook_buf[8192];
    char log_buf[1024];
    char line_buf[4096];
} api_mem;

/* ---------- JSON output ---------- */
typedef struct { char *buf; unsigned cap, at; int ok; } OcJson;

static void j_init(OcJson *j, char *buf, unsigned cap) { j->buf=buf; j->cap=cap; j->at=0; j->ok=1; buf[0]=0; }
static void j_raw(OcJson *j, const char *s) {
    unsigned n=oc_length(s);
    if (!j->ok || j->at+n>=j->cap) { j->ok=0; return; }
    for (unsigned i=0; i<n; ++i) j->buf[j->at++]=s[i];
    j->buf[j->at]=0;
}
static void j_str(OcJson *j, const char *s) {
    j_raw(j,"\"");
    for (; j->ok && *s; ++s) {
        if (*s=='\\' || *s=='"') {
            if (j->at+2>=j->cap) { j->ok=0; return; }
            j->buf[j->at++]='\\'; j->buf[j->at++]=*s;
        } else {
            if (j->at+1>=j->cap) { j->ok=0; return; }
            j->buf[j->at++]=*s;
        }
    }
    if (j->ok) j->buf[j->at]=0;
    j_raw(j,"\"");
}
static __attribute__((noinline)) void j_kv(OcJson *j, char kind, const char *k, const char *v) {
    if (!j->at) j_raw(j,"{");
    else if (j->buf[j->at-1]!='{') j_raw(j,",");
    j_str(j,k); j_raw(j,":");
    if (kind=='s') j_str(j,v);
    else j_raw(j,kind=='b'?(v?"true":"false"):v);
}
#define j_kv_str(j,k,v) j_kv((j),'s',(k),(v))
#define j_kv_raw(j,k,v) j_kv((j),'r',(k),(v))
#define j_kv_bool(j,k,v) j_kv((j),'b',(k),(v)?"1":0)

static __attribute__((noinline)) void j_kvs(OcJson *j, const char *types, const char *keys, const char *const *vals) {
    for (unsigned i=0; types[i]; ++i) {
        j_kv(j,types[i],keys,vals[i]);
        keys+=oc_length(keys)+1;
    }
}

static char *oc_find_str(char *s, const char *sub) {
    for (; *s; ++s) if (oc_prefix(s,sub)) return s;
    return 0;
}
static int oc_rec_settled(char **rec) {
    return oc_equal(rec[6],"-") && oc_equal(rec[7],"-") &&
        (oc_equal(rec[1],"active") || oc_equal(rec[1],"removed"));
}
static int oc_session_is_closed(const char *session_dir) {
    long sfd=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    int cl=sfd>=0 && !oc_absent_at((int)sfd,"closed");
    if (sfd>=0) (void)oc_close((int)sfd);
    return cl;
}

static int emit_fail(const char *err) {
    OcJson j; j_init(&j,api_mem.json,sizeof api_mem.json);
    j_kv_bool(&j,"ok",0); j_kv_str(&j,"error",err); j_raw(&j,"}\n");
    if (j.ok) (void)oc_write_all(1,j.buf,j.at);
    return OC_API_ERR;
}

static inline void oc_u32_dec(unsigned v, char out[24]) { oc_u64_dec((oc_u64)v,out); }
static inline int oc_run_prog(const char *path, char *const argv[], int out_fd,
                              char *cap_buf, unsigned cap_sz, int keep_fd) {
    return oc_run_cmd(path,argv,out_fd,cap_buf,cap_sz,keep_fd);
}

/* ---------- Small streaming line reader (with optional single-pass SHA-256) ---------- */
typedef struct { int fd; char buf[4096]; unsigned at, filled, total, limit; OcHash *hash; } OcStream;

static int oc_stream_line(OcStream *s, char *out, unsigned cap, int *had_nl) {
    unsigned n=0; *had_nl=0;
    for (;;) {
        if (s->at==s->filled) {
            long r=oc_read(s->fd,s->buf,sizeof s->buf);
            if (r==-4) continue;
            if (r<0) return -1;
            if (!r) { out[n]=0; return n?1:0; }
            if (s->hash) oc_hash_add(s->hash,s->buf,(unsigned)r);
            s->at=0; s->filled=(unsigned)r;
        }
        char c=s->buf[s->at++];
        if (++s->total > s->limit) return -1;
        if (c=='\n') { out[n]=0; *had_nl=1; return 1; }
        if (n+1>=cap) return -1;
        out[n++]=c;
    }
}

/* ---------- Filesystem / identity helpers ---------- */
static int oc_verify_file_sha(int dir, const char *name, const char *expected, oc_u64 limit) {
    char dig[65]; OcMeta fm;
    return expected && oc_hash_file_at(dir,name,dig,&fm) && fm.size<=limit && oc_equal(dig,expected);
}

static int oc_read_hex64_file(int dir, const char *name, char out[65]) {
    long fd=oc_openat(dir,name,OC_READ,0);
    if (fd<0) return 0;
    OcMeta m; char buf[66];
    int ok=oc_stat((int)fd,&m)>=0 && (m.mode&OC_TYPE)==OC_REGULAR && m.size==65;
    int n=ok?oc_text_fd((int)fd,buf,sizeof buf):-1;
    if (oc_close((int)fd)<0) ok=0;
    if (!ok || n!=65 || !oc_one_line(buf) || !oc_hex(buf,64)) return 0;
    for (unsigned i=0; i<65; ++i) out[i]=buf[i];
    return 1;
}

static int oc_read_boot_id(int ram, long owner, long group, char out[37]) {
    OcMeta m;
    if (oc_metadata(ram,"boot-id",&m)<0 || (m.mode&OC_TYPE)!=0120000 ||
        m.size!=36 || m.uid!=(unsigned)owner || m.gid!=(unsigned)group) return 0;
    long n=oc_readlink(ram,"boot-id",out,36);
    if (n!=36) return 0;
    out[36]=0;
    return oc_uuid(out);
}

static int oc_read_version_file(int dir, const char *expect_digest, char out[64]) {
    if (expect_digest) { if (!oc_verified_text(dir,"VERSION",expect_digest,out,64)) return 0; }
    else if (oc_text(dir,"VERSION",out,64,0)<=0) return 0;
    if (!oc_one_line(out) || !*out) return 0;
    for (const char *s=out; *s; ++s) {
        char c=*s;
        if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='-')) return 0;
    }
    return 1;
}

static int oc_open_pkg_verified(int data, const char *pkg_id, OcManifest *mf) {
    char rel[96];
    int pdir=(oc_hex(pkg_id,64) && oc_join(rel,sizeof rel,"packages/",pkg_id)) ? oc_open_private(data,rel) : -1;
    if (pdir<0) return -1;
    if (!oc_verified_text(pdir,"files.sha256",pkg_id,api_mem.mf_buf,sizeof api_mem.mf_buf) ||
        !oc_manifest(api_mem.mf_buf,mf,0)) { (void)oc_close(pdir); return -1; }
    return pdir;
}

static int oc_package_version(int data, const char *pkg_id, char out[64]) {
    OcManifest mf;
    int pdir=oc_open_pkg_verified(data,pkg_id,&mf);
    if (pdir<0) return 0;
    const char *vd=oc_digest(&mf,"VERSION");
    int ok=vd && oc_read_version_file(pdir,vd,out);
    if (oc_close(pdir)<0) ok=0;
    return ok;
}

static int oc_load_package_catalog(int data, const char *pkg_id, char *buf, unsigned cap, OcCatalog *cat) {
    OcManifest mf;
    int pdir=oc_open_pkg_verified(data,pkg_id,&mf);
    if (pdir<0) return 0;
    const char *sd=oc_digest(&mf,"services.tsv");
    int ok=sd && oc_verified_text(pdir,"services.tsv",sd,buf,cap) &&
        oc_catalog_load(buf,oc_length(buf),cat);
    if (oc_close(pdir)<0) ok=0;
    return ok;
}

static int oc_any_entry_cb(const char *name, void *raw) { (void)name; *(int *)raw=1; return 0; }
static int oc_is_dir_empty(int dir) {
    int nonempty=0;
    return oc_dir_iter(dir,oc_any_entry_cb,&nonempty) && !nonempty;
}

typedef struct {
    int valid, has_access;
    char cfg_buf[1024], acc_buf[320];
    OcPrefs prefs;
    char *acc_fields[6];
} OcSnapInfo;

static int oc_snap_read(int data, const char *snap_id, OcSnapInfo *out,
                        OcCatalog *cat_opt, char *cat_buf, unsigned cat_cap,
                        int verify_all, const char *cat_pkg_override) {
    out->valid=0; out->has_access=0;
    char rel[96];
    int sdir=(oc_hex(snap_id,64) && oc_join(rel,sizeof rel,"snapshots/",snap_id)) ? oc_open_private(data,rel) : -1;
    if (sdir<0) return 0;
    char mf_buf[4096]; OcManifest mf;
    int ok=oc_verified_text(sdir,"files.sha256",snap_id,mf_buf,sizeof mf_buf) && oc_manifest(mf_buf,&mf,0);
    if (ok && verify_all) {
        ok=oc_members(sdir,&mf,1);
        for (unsigned i=0; ok && i<mf.count; ++i) {
            const char *nm=mf.rows[i].name;
            if (oc_equal(nm,"config") || oc_equal(nm,"access")) continue;
            ok=oc_verify_file_sha(sdir,nm,mf.rows[i].digest,33554432);
        }
    }
    const char *cd=ok?oc_digest(&mf,"config"):0;
    if (ok) ok=cd && oc_verified_text(sdir,"config",cd,out->cfg_buf,sizeof out->cfg_buf);
    if (ok) {
        if (oc_prefix(out->cfg_buf,"OC2\n")) {
            char tmp_cfg[1024]; OcPrefs pre;
            ok=oc_join(tmp_cfg,sizeof tmp_cfg,"",out->cfg_buf) && oc_prefs_parse(tmp_cfg,0,1,&pre);
            const char *cpkg=(cat_pkg_override && *cat_pkg_override) ? cat_pkg_override : pre.package;
            if (ok && cat_opt) ok=oc_load_package_catalog(data,cpkg,cat_buf,cat_cap,cat_opt);
            if (ok) ok=oc_prefs_parse(out->cfg_buf,cat_opt,1,&out->prefs);
        } else {
            ok=oc_prefs_parse(out->cfg_buf,0,0,&out->prefs);
        }
    }
    if (ok) {
        const char *ad=oc_digest(&mf,"access");
        if (ad) {
            ok=oc_digest(&mf,"runlogin") && oc_digest(&mf,"sshd.conf") &&
               oc_verified_text(sdir,"access",ad,out->acc_buf,sizeof out->acc_buf) &&
               oc_access(out->acc_buf,out->acc_fields);
            out->has_access=1;
        } else if (!oc_absent_at(sdir,"access")) {
            ok=0;
        }
    }
    if (oc_close(sdir)<0) ok=0;
    out->valid=ok;
    return ok;
}

static OcSnapInfo api_snap_a, api_snap_b;

static int oc_snap_package_only(int data, const char *snap_id, char pkg_out[65]) {
    return oc_snap_read(data,snap_id,&api_snap_b,0,0,0,0,0) && oc_join(pkg_out,65,"",api_snap_b.prefs.package);
}

static int oc_key_fingerprint(const char *root_path, const char *key_id, char out[128]) {
    char dbase[320], kpath[512], raw[512];
    if (!oc_data_base(root_path,dbase,sizeof dbase) ||
        !oc_join4(kpath,sizeof kpath,dbase,"/keys/",key_id,".cmu")) return 0;
    const char *prog="/usr/bin/ssh-keygen";
#ifdef OC_HOST
    const char *hp=getenv("OC_HOST_SSH_KEYGEN");
    if (hp && *hp) prog=hp;
#endif
    char *argv[]={(char *)prog,"-l","-f",kpath,0};
    if (oc_run_prog(prog,argv,-1,raw,sizeof raw,-1)!=0) return 0;
    char *p=raw;
    while (*p==' '||*p=='\t') ++p;
    while (*p && *p!=' ' && *p!='\t' && *p!='\n') ++p;
    while (*p==' '||*p=='\t') ++p;
    unsigned n=0;
    while (*p && *p!=' ' && *p!='\t' && *p!='\n' && n+1<128) {
        char c=*p++;
        if (!((c>='a'&&c<='f')||(c>='0'&&c<='9')||c==':')) return 0;
        out[n++]=c;
    }
    out[n]=0;
    return n>0 && (*p==' '||*p=='\t'||*p=='\n'||!*p);
}

static int oc_factory_wireless(int root, const char *root_path) {
#ifdef OC_HOST
    const char *wf=getenv("OC_HOST_WIRELESS_FILE");
    if (wf && *wf) { OcMeta wm; return oc_metadata(OC_CWD,wf,&wm)<0 ? 1 : 0; }
#endif
    long fd=oc_beneath(root,"jci/scripts/get_board_type.sh",OC_READ,0);
    if (fd<0) return 2;
    char dig[65]; OcMeta m;
    int ok=oc_hash_copy((int)fd,-1,65536,dig,&m)==OC_COPY_OK &&
        oc_equal(dig,oc_pin_digest("root/board.sh","2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da"));
    if (oc_close((int)fd)<0) ok=0;
    if (!ok) return 2;
    char spath[512];
    if (!oc_join(spath,sizeof spath,oc_equal(root_path,"/")?"":root_path,"/jci/scripts/get_board_type.sh")) return 2;
    char *argv[]={"sh",spath,0};
    int wrc=oc_run_prog("/bin/sh",argv,-1,0,0,-1);
    return wrc<0 ? 2 : (wrc==2 ? 0 : 1);
}

/* ---------- Status view JSON renderer ---------- */
static int oc_api_emit_status_view(int root, const char *root_path, int data, int ram,
                                   const char *session_dir, long owner, long group,
                                   int exists, int empty_state, char *rec[13],
                                   const char *settings_pkg, const char *sel_snap,
                                   int conflict, int removed_now) {
    int installed=0, retained=0, restart=removed_now, pending=empty_state, restart_fixed=0;
    int developer=0, uart_cur=0, ssh_cur=0, wl_cur=0, as_cur=0, has_as=0, has_oc2=0;
    int has_touch_cur=0, has_base_cur=0, has_pandora=0, has_base=0, has_wl=0;
    const char *rev="-", *notice="-", *touch="0", *warning="0", *uart="0", *owner_ssh="0";
    const char *key="-", *pandora="", *base="", *wireless="", *autoshow="";
    const char *touch_cur="", *warning_cur="", *base_cur="", *sel_key="-";
    char inst_ver[64], run_ver[64], fp[128], acc_sel[65];
    int has_acc_sel=oc_read_hex64_file(ram,"access-selected",acc_sel);
    (void)oc_join(inst_ver,sizeof inst_ver,"","-");
    (void)oc_join(fp,sizeof fp,"","-");

    static OcSnapInfo v_snap;
    OcSnapInfo *s_snap=&api_snap_a, *a_snap=&api_snap_b;
    OcCatalog cat; cat.count=0;
    int s_snap_loaded=0, sel_wl=0;

    if (!exists && !oc_absent_at(ram,"selected")) { restart=1; restart_fixed=1; }
    if (exists) {
        rev=rec[5]; notice=rec[12];
        int settled=oc_rec_settled(rec);
        if (oc_equal(rec[1],"purge")) {
            rev=rec[2]; restart=1; restart_fixed=1; pending=1;
        } else {
            const char *view_id=rec[5];
            if (settings_pkg && *settings_pkg) {
                char cur_pkg[65];
                if (sel_snap && *sel_snap && oc_equal(rec[5],sel_snap)) (void)oc_join(cur_pkg,sizeof cur_pkg,"",settings_pkg);
                else if (!oc_snap_package_only(data,rec[5],cur_pkg)) return emit_fail("invalid_snapshot");
                if (!oc_equal(cur_pkg,settings_pkg)) { view_id=sel_snap; restart=1; restart_fixed=1; }
            }
            if (!oc_snap_read(data,view_id,&v_snap,&cat,api_mem.cat_buf,sizeof api_mem.cat_buf,1,settings_pkg))
                return emit_fail("invalid_snapshot");
            touch=v_snap.prefs.touch; warning=v_snap.prefs.warning;
            if (v_snap.prefs.is_oc2) {
                has_oc2=1; pandora=v_snap.prefs.pandora; has_pandora=1;
                base=v_snap.prefs.base; has_base=1; wireless=v_snap.prefs.wireless; has_wl=1;
                if (v_snap.prefs.has_autoshow) { autoshow=v_snap.prefs.autoshow; has_as=1; }
            }
            if (v_snap.has_access) {
                developer=1; uart=v_snap.acc_fields[0]; owner_ssh=v_snap.acc_fields[1]; key=v_snap.acc_fields[2];
                if (!oc_equal(key,"-") && oc_access_key_verify(data,key,owner,group)) {
                    if (!oc_key_fingerprint(root_path,key,fp)) (void)oc_join(fp,sizeof fp,"","-");
                }
            }
            installed=oc_equal(rec[1],"active"); retained=oc_equal(rec[1],"removed");
            if (installed && !conflict && !oc_package_version(data,v_snap.prefs.package,inst_ver))
                (void)oc_join(inst_ver,sizeof inst_ver,"","-");
            if (installed) { if (!sel_snap || !oc_equal(sel_snap,rec[5])) restart=1; }
            else if (!oc_absent_at(ram,"selected")) { restart=1; restart_fixed=1; }
            if (!settled) { restart=1; restart_fixed=1; pending=1; rev=rec[2]; }
            if (has_acc_sel && oc_equal(acc_sel,view_id)) {
                uart_cur=oc_equal(uart,"1"); ssh_cur=oc_equal(owner_ssh,"1"); sel_key=key;
            }
            if (sel_snap && *sel_snap && oc_equal(sel_snap,view_id)) {
                s_snap_loaded=1; sel_wl=oc_equal(v_snap.prefs.wireless,"1"); as_cur=oc_equal(v_snap.prefs.autoshow,"1");
                touch_cur=touch; warning_cur=warning; base_cur=base; has_touch_cur=1; if (has_base) has_base_cur=1;
            } else if (sel_snap && *sel_snap && oc_snap_read(data,sel_snap,s_snap,0,0,0,1,settings_pkg)) {
                s_snap_loaded=2; sel_wl=oc_equal(s_snap->prefs.wireless,"1"); as_cur=oc_equal(s_snap->prefs.autoshow,"1");
                touch_cur=s_snap->prefs.touch; warning_cur=s_snap->prefs.warning; has_touch_cur=1;
                if (s_snap->prefs.is_oc2) { base_cur=s_snap->prefs.base; has_base_cur=1; }
                if (has_acc_sel && oc_equal(acc_sel,sel_snap) && s_snap->has_access) {
                    uart_cur=oc_equal(s_snap->acc_fields[0],"1"); ssh_cur=oc_equal(s_snap->acc_fields[1],"1");
                    sel_key=s_snap->acc_fields[2];
                }
            } else if (installed) restart_fixed=1;
            if (has_acc_sel && !oc_equal(acc_sel,view_id) && (!sel_snap || !oc_equal(acc_sel,sel_snap))) {
                if (oc_snap_read(data,acc_sel,a_snap,0,0,0,1,settings_pkg) && a_snap->has_access) {
                    uart_cur=oc_equal(a_snap->acc_fields[0],"1"); ssh_cur=oc_equal(a_snap->acc_fields[1],"1");
                    sel_key=a_snap->acc_fields[2];
                }
            }
            if (developer && !oc_equal(key,sel_key) && oc_equal(owner_ssh,"1")) restart_fixed=1;
        }
    }
    int wl_factory=0;
    if (has_wl) {
        int fw=oc_factory_wireless(root,root_path);
        if (fw==2) return emit_fail("wireless_unavailable");
        wl_factory=(fw==0);
        if (sel_wl) {
            char wa[16];
            if (oc_text(ram,"feature/wireless-applied",wa,sizeof wa,0)>0 && oc_one_line(wa) && oc_equal(wa,"1")) wl_cur=1;
        }
        if ((oc_equal(wireless,"1")?1:0)!=wl_cur) restart=1;
    }
    if (has_as && (oc_equal(autoshow,"1")?1:0)!=as_cur) restart=1;

    long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    int vok=sdir>=0 && oc_read_version_file((int)sdir,0,run_ver);
    if (sdir>=0) (void)oc_close((int)sdir);
    if (!vok) return emit_fail("invalid_version");

    OcJson j; j_init(&j,api_mem.json,sizeof api_mem.json);
    const char *kv[20]={
        "1",rev,installed?"1":0,retained?"1":0,0,conflict?"1":0,restart?"1":0,pending?"1":0,
        touch,warning,notice,run_ver,inst_ver,developer?"1":0,
        uart,owner_ssh,key,fp,uart_cur?"1":"0",ssh_cur?"1":"0"
    };
    j_kvs(&j,"bsbbbbbbrrsssbrrssrr",
          "ok\0revision\0installed\0retained\0undo\0conflict\0restart\0pending\0"
          "touch\0warning\0notice\0version\0installedVersion\0developer\0"
          "uart\0ssh\0key\0fingerprint\0uartCurrent\0sshCurrent",kv);
    if (has_pandora) j_kv_raw(&j,"pandora",pandora);
    if (has_base) {
        j_kv_raw(&j,"base",base);
        if (has_base_cur) j_kv_raw(&j,"baseCurrent",base_cur);
    }
    if (has_touch_cur) {
        j_kv_raw(&j,"touchCurrent",touch_cur);
        j_kv_raw(&j,"warningCurrent",warning_cur);
    }
    j_kv_bool(&j,"restartFixed",restart_fixed);
    if (has_wl) {
        j_kv_raw(&j,"wireless",wireless);
        j_kv_raw(&j,"wirelessCurrent",wl_cur?"1":"0");
        j_kv_bool(&j,"wirelessFactory",wl_factory);
    }
    if (has_oc2) {
        OcPrefs *sp = s_snap_loaded==1 ? &v_snap.prefs : (s_snap_loaded==2 ? &s_snap->prefs : 0);
        j_raw(&j,",\"services\":[");
        for (unsigned i=0; i<cat.count; ++i) {
            j_raw(&j,i?",{":"{");
            const char *cur_val="null";
            if (sp && sp->is_oc2) {
                for (unsigned k=0; k<sp->svc_count; ++k)
                    if (oc_equal(sp->svc_ids[k],cat.rows[i].id)) { cur_val=sp->svc_vals[k]; break; }
            }
            j_kv_str(&j,"id",cat.rows[i].id);
            j_kv_str(&j,"label",cat.rows[i].label);
            j_kv_raw(&j,"saved",v_snap.prefs.svc_vals[i]);
            j_kv_raw(&j,"current",cur_val);
            j_kv_str(&j,"enable",cat.rows[i].enable);
            j_kv_str(&j,"disable",cat.rows[i].disable);
            j_raw(&j,"}");
        }
        j_raw(&j,"]");
    }
    if (has_as) {
        j_kv_raw(&j,"carplayAutoshow",autoshow);
        j_kv_raw(&j,"carplayAutoshowCurrent",as_cur?"1":"0");
    }
    j_kv_bool(&j,"completionReady",0);
    j_raw(&j,"}\n");
    return (j.ok && oc_write_all(1,j.buf,j.at)) ? OC_API_DONE : emit_fail("state_changed");
}

/* ---------- Streaming native index.html renderer (buffered line writes) ---------- */
static int oc_write_str(int fd, const char *s) { return oc_write_all(fd,s,oc_length(s)); }

static __attribute__((noinline)) int oc_render_index_native(int pkg_fd, OcManifest *pkg_mf, int comp_fd, OcManifest *comp_mf,
                                  int work_fd, const OcPrefs *p) {
    const char *tpl_name=oc_equal(p->warning,"1")?"index-on.html":"index-off.html";
    const char *tpl_dig=oc_digest(comp_mf,tpl_name);
    if (!tpl_dig) return 0;

    int is_base=oc_equal(p->base,"1"), is_warn=oc_equal(p->warning,"1"), is_as=oc_equal(p->autoshow,"1");
    int aa_off=0, pandora_off=0, sxm_off=0;
    for (unsigned i=0; i<p->svc_count; ++i) {
        if (oc_equal(p->svc_ids[i],"android-auto") && oc_equal(p->svc_vals[i],"0")) aa_off=1;
        if (oc_equal(p->svc_ids[i],"pandora") && oc_equal(p->svc_vals[i],"0")) pandora_off=1;
        if (oc_equal(p->svc_ids[i],"siriusxm") && oc_equal(p->svc_vals[i],"0")) sxm_off=1;
    }
    char h[160]; h[0]=0;
    if (is_base) (void)oc_join(h,sizeof h,h,"stitcher,dab,tv,aharadio,dvd,");
    if (pandora_off) (void)oc_join(h,sizeof h,h,"pandora,");
    if (sxm_off) (void)oc_join(h,sizeof h,h,"satradio,xmaudio,xmdata,");
    int ag=is_base && aa_off;
    if (ag) (void)oc_join(h,sizeof h,h,"androidauto,");
    unsigned hlen=oc_length(h);
    if (hlen && h[hlen-1]==',') h[--hlen]=0;
    int nd=is_warn || hlen>0;

    if (nd && !oc_verified_text(pkg_fd,"system-hook.js",oc_digest(pkg_mf,"system-hook.js"),api_mem.hook_buf,sizeof api_mem.hook_buf)) return 0;
    if (is_base && !oc_verified_text(pkg_fd,"base-logging.js",oc_digest(pkg_mf,"base-logging.js"),api_mem.log_buf,sizeof api_mem.log_buf)) return 0;

    long tfd=oc_openat(comp_fd,tpl_name,OC_READ,0);
    if (tfd<0) return 0;
    OcMeta tm;
    if (oc_stat((int)tfd,&tm)<0 || (tm.mode&OC_TYPE)!=OC_REGULAR) { (void)oc_close((int)tfd); return 0; }
    long ofd=oc_openat(work_fd,"index.html",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (ofd<0) { (void)oc_close((int)tfd); return 0; }

    OcHash th; oc_hash_init(&th);
    OcStream st; st.fd=(int)tfd; st.at=st.filled=st.total=0; st.limit=262144; st.hash=&th;
    unsigned lg=0, hk=0, ap=0, tok_cnt=0;
    int ok=1, had_nl=0, r;
    while (ok && (r=oc_stream_line(&st,api_mem.line_buf,sizeof api_mem.line_buf,&had_nl))==1) {
        char *line=api_mem.line_buf;
        for (const char *s=line; *s; ++s) if (oc_prefix(s,"@TOKEN@")) ++tok_cnt;
        int is_log=is_base && oc_find_str(line,"src=\"common/js/logDefaults.js\"")!=0;
        if (is_log) {
            ok=oc_write_str((int)ofd,line) && oc_write_str((int)ofd,"\n<script>\n") &&
               oc_write_str((int)ofd,api_mem.log_buf);
            unsigned lb=oc_length(api_mem.log_buf);
            if (ok && (!lb || api_mem.log_buf[lb-1]!='\n')) ok=oc_write_str((int)ofd,"\n");
            if (ok) ok=oc_write_str((int)ofd,"</script>\n");
            ++lg; continue;
        }
        if (oc_find_str(line,"framework.init();")) {
            if (nd) {
                int ab=0;
                char *hp=api_mem.hook_buf;
                while (ok && *hp) {
                    char *hl=hp;
                    while (*hp && *hp!='\n') ++hp;
                    if (*hp=='\n') *hp++=0;
                    if (oc_find_str(hl,"/* OPEN_CONNECT_AA_BEGIN */")) { ab=1; continue; }
                    if (oc_find_str(hl,"/* OPEN_CONNECT_AA_END */")) { ab=0; continue; }
                    char *call_pos=oc_find_str(hl," /* OPEN_CONNECT_AA_CALL */");
                    int has_call=call_pos!=0 || oc_find_str(hl,"/* OPEN_CONNECT_AA_CALL */")!=0;
                    if (!ag && (ab || has_call)) continue;
                    char *ap_pos=oc_find_str(hl,"/*OPEN_CONNECT_APPLIED*/");
                    while (*hl==' '||*hl=='\t') ++hl;
                    OcJson lj; j_init(&lj,api_mem.json,sizeof api_mem.json);
                    for (char *s=hl; lj.ok && *s; ) {
                        if (call_pos && s==call_pos) { s+=27; call_pos=0; continue; }
                        if (ap_pos && s==ap_pos) {
                            j_raw(&lj,p->warning); j_raw(&lj,",\""); j_raw(&lj,h); j_raw(&lj,"\"");
                            s+=24; ap_pos=0; ++ap; continue;
                        }
                        if (lj.at+1>=lj.cap) { lj.ok=0; break; }
                        lj.buf[lj.at++]=*s++;
                    }
                    j_raw(&lj,"\n");
                    ok=lj.ok && oc_write_all((int)ofd,lj.buf,lj.at);
                }
                ++hk;
            }
            if (ok && is_as) {
                ok=oc_write_str((int)ofd,"</script>\n<script src=\"file:///tmp/open-connect/feature/carplay.js\"></script>\n<script>\n");
            }
        }
        if (ok) ok=oc_write_str((int)ofd,line) && (!had_nl || oc_write_all((int)ofd,"\n",1));
    }
    char got_dig[65]; oc_hash_finish(&th,got_dig);
    if (r<0 || (oc_u64)st.total!=tm.size || !oc_equal(got_dig,tpl_dig)) ok=0;
    if (ok) ok=oc_mode((int)ofd,0600)>=0 && oc_sync((int)ofd)>=0;
    if (oc_close((int)ofd)<0) ok=0;
    (void)oc_close((int)tfd);
    return ok && (!is_base || lg==1) && (!nd || (hk==1 && ap==1)) && tok_cnt==1;
}

/* ---------- Cleanup & package boot-select verification ---------- */
static inline void oc_cleanup_work(int snaps_fd, const char *work_leaf) { oc_rm_subdir(snaps_fd,work_leaf); }

static inline int oc_verify_pkg_boot_select(int data, const char *root_path, const char *pkg_id,
                                            long owner, long group, char bs_path[512]) {
    return oc_pkg_boot_select(data,root_path,pkg_id,owner,group,bs_path);
}

static int oc_check_session_pointer(int ram, const char *session_dir, const char *ptr_name) {
    char link[512];
    long n=oc_readlink(ram,ptr_name,link,sizeof link-1);
    if (n<=0 || (unsigned)n>=sizeof link-1) return 0;
    link[n]=0;
    return oc_equal(link,session_dir);
}

static int oc_session_mf_matches(const char *session_dir, const char *pkg_id) {
    long sfd=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    if (sfd<0) return 0;
    int ok=oc_verify_file_sha((int)sfd,"files.sha256",pkg_id,65536);
    (void)oc_close((int)sfd);
    return ok;
}

static int oc_mark_closed(const char *session_dir) {
    long sfd=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    if (sfd<0) return 0;
    OcMeta cm;
    long cfd=oc_openat((int)sfd,"closed",OC_WRITE|OC_CREATE,0600);
    int ok=cfd>=0 && oc_stat((int)cfd,&cm)>=0 && (cm.mode&OC_TYPE)==OC_REGULAR;
    if (cfd>=0 && oc_close((int)cfd)<0) ok=0;
    if (oc_close((int)sfd)<0) ok=0;
    return ok;
}

static int oc_run_awk_profile(const char *dbase, const char *pkg_id, const char *cfg_path,
                              const char *cfg_bytes, const char *cat_bytes,
                              const char *script_name, const char *ui_mode, const char *in_path,
                              int out_dir, const char *out_name) {
    char pdir[256], prefs_awk[320], sc_awk[320], cat_arg[320], mod_arg[320];
    char cb_arg[48], ib_arg[48], in_arg[320], mode_arg[32];
    if (!oc_join4(pdir,sizeof pdir,dbase,"/packages/",pkg_id,0) ||
        !oc_join(prefs_awk,sizeof prefs_awk,pdir,"/preferences.awk") ||
        !oc_join4(sc_awk,sizeof sc_awk,pdir,"/",script_name,0) ||
        !oc_join4(cat_arg,sizeof cat_arg,"catalog=",pdir,"/services.tsv",0) ||
        !oc_join(cb_arg,sizeof cb_arg,"catalog_bytes=",cat_bytes) ||
        !oc_join(in_arg,sizeof in_arg,"input=",cfg_path) || !oc_join(ib_arg,sizeof ib_arg,"input_bytes=",cfg_bytes)) return 0;
    long ofd=oc_openat(out_dir,out_name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (ofd<0) return 0;
    const char *awk_bin="/bin/busybox";
#ifdef OC_HOST
    awk_bin=getenv("OC_HOST_AWK");
    if (!awk_bin || !*awk_bin) awk_bin="/usr/bin/awk";
#endif
    char *argv[24]; unsigned n=0;
    argv[n++]="awk"; argv[n++]="-v"; argv[n++]="operation=compose";
    if (ui_mode) {
        if (!oc_join4(mod_arg,sizeof mod_arg,"modules=",pdir,"/ui-modules.tsv",0) ||
            !oc_join(mode_arg,sizeof mode_arg,"ui_mode=",ui_mode)) { (void)oc_close((int)ofd); return 0; }
        argv[n++]="-v"; argv[n++]=mode_arg; argv[n++]="-v"; argv[n++]=mod_arg;
    }
    argv[n++]="-v"; argv[n++]=cat_arg; argv[n++]="-v"; argv[n++]=cb_arg;
    argv[n++]="-v"; argv[n++]=in_arg; argv[n++]="-v"; argv[n++]=ib_arg;
    argv[n++]="-f"; argv[n++]=prefs_awk; argv[n++]="-f"; argv[n++]=sc_awk;
    argv[n++]=(char *)in_path; argv[n]=0;
    int rc=oc_run_prog(awk_bin,argv,(int)ofd,0,0,-1);
    int ok=(rc==0) && oc_mode((int)ofd,0600)>=0;
    if (oc_close((int)ofd)<0) ok=0;
    return ok;
}

static int oc_open_composed_verified(int data_fd, const char *pkg_id, const char *snap_id,
                                     char cmf_buf[4096], OcManifest *cmf) {
    char crel[96], spath[128], dep_key[96]; OcManifest dmf, smf;
    int cdir=oc_join(crel,sizeof crel,"composed/",pkg_id)?oc_open_private(data_fd,crel):-1;
    int cs_fd=oc_join(spath,sizeof spath,"snapshots/",snap_id)?oc_open_private(data_fd,spath):-1;
    int cok=cdir>=0 && cs_fd>=0 &&
        oc_verified_text(cs_fd,"files.sha256",snap_id,oc_mscratch,sizeof oc_mscratch) && oc_manifest(oc_mscratch,&smf,0) &&
        oc_saved_text(cs_fd,&smf,"dependencies",oc_big_buf,sizeof oc_big_buf) && oc_manifest(oc_big_buf,&dmf,1) &&
        oc_join4(dep_key,sizeof dep_key,"composed-",pkg_id,"/files.sha256",0);
    const char *cdig=cok?oc_digest(&dmf,dep_key):0;
    if (cs_fd>=0) (void)oc_close(cs_fd);
    if (!cok || !cdig || !oc_verified_text(cdir,"files.sha256",cdig,cmf_buf,4096) || !oc_manifest(cmf_buf,cmf,0)) {
        if (cdir>=0) (void)oc_close(cdir);
        return -1;
    }
    return cdir;
}

int oc_render_sm_profiles(int data_fd, const char *root_path, const char *pkg_id,
                          const char *snap_id, const char *cfg_path, unsigned cfg_len,
                          const char *warning_val, int out_dir) {
    OcManifest pmf, cmf; char cmf_buf[4096], dbase[320], cfg_len_s[24], cat_len_s[24];
    int pdir=oc_open_pkg_verified(data_fd,pkg_id,&pmf);
    if (pdir<0) return 0;
    const char *nf[3]={"preferences.awk","services.tsv","sm-profile.awk"};
    int ok=1;
    for (unsigned i=0; ok&&i<3; ++i)
        ok=oc_verify_file_sha(pdir,nf[i],oc_digest(&pmf,nf[i]),262144);
    OcMeta cat_m={0};
    long cfd=ok?oc_openat(pdir,"services.tsv",OC_READ,0):-1;
    if (cfd<0 || oc_stat((int)cfd,&cat_m)<0) ok=0;
    if (cfd>=0) (void)oc_close((int)cfd);
    (void)oc_close(pdir);
    int cdir=ok?oc_open_composed_verified(data_fd,pkg_id,snap_id,cmf_buf,&cmf):-1;
    if (cdir<0) return 0;
    oc_u64_dec((oc_u64)cfg_len,cfg_len_s); oc_u64_dec(cat_m.size,cat_len_s);
    ok=oc_data_base(root_path,dbase,sizeof dbase);
    const char *st=oc_equal(warning_val,"1")?"on":"off";
    const char *profs[2]={"normal","wcp"};
    for (unsigned i=0; ok&&i<2; ++i) {
        char tnm[32], onm[32], tin[320];
        ok=oc_join4(tnm,sizeof tnm,"sm-",profs[i],"-",st) &&
            oc_join(tnm,sizeof tnm,tnm,".conf") &&
            oc_join4(onm,sizeof onm,"sm-",profs[i],".conf",0) &&
            oc_verify_file_sha(cdir,tnm,oc_digest(&cmf,tnm),262144) &&
            oc_join4(tin,sizeof tin,dbase,"/composed/",pkg_id,"/") &&
            oc_join(tin,sizeof tin,tin,tnm) &&
            oc_run_awk_profile(dbase,pkg_id,cfg_path,cfg_len_s,cat_len_s,"sm-profile.awk",0,tin,out_dir,onm);
    }
    if (oc_close(cdir)<0) ok=0;
    return ok;
}

/* ---------- Main HTTP interactive handler (single clean cleanup epilogue) ---------- */
static int oc_load_state(int root, long owner, long group, int *data_out, int *exists_out,
                         int *empty_out, char rec_buf[1024], char *rec[13], const char **err_out) {
    *data_out=-1; *exists_out=0; *empty_out=0;
    if (oc_data_absent(root)) return 1;
    int data=oc_open_data_dir(root);
    if (data<0) { *err_out="invalid_state_directory"; return 0; }
    *data_out=data;
    if (!oc_absent_at(data,"record")) {
        if (!oc_record_read_any(data,owner,group,rec_buf,1024,rec)) { *err_out="invalid_record"; return 0; }
        *exists_out=1;
        return 1;
    }
    if (oc_is_dir_empty(data)) { *empty_out=1; return 1; }
    *err_out="invalid_record";
    return 0;
}

static int oc_api_uptime_cs(int root, oc_u64 *out_cs) {
    char buf[64];
    if (oc_text(root,"proc/uptime",buf,sizeof buf,1)<=0) return 0;
    oc_u64 sec=0, frac=0; unsigned fd=0;
    const char *p=buf;
    if (*p<'0'||*p>'9') return 0;
    while (*p>='0'&&*p<='9') { sec=sec*10+(unsigned)(*p-'0'); ++p; }
    if (*p=='.') {
        ++p;
        while (*p>='0'&&*p<='9'&&fd<2) { frac=frac*10+(unsigned)(*p-'0'); ++fd; ++p; }
        while (fd<2) { frac*=10; ++fd; }
    }
    *out_cs=sec*100+frac;
    return 1;
}

static int oc_usb_retained(int root, const char *session_dir, const char *expect_rev) {
    if (!expect_rev) return 0;
    long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    if (sdir<0) return 0;
    OcMeta m={0}; char target[128];
    int ok=oc_metadata((int)sdir,"admitted",&m)>=0 && (m.mode&OC_TYPE)==0120000 &&
        m.size>0 && m.size<sizeof target;
    long n=ok?oc_readlink((int)sdir,"admitted",target,sizeof target-1):-1;
    (void)oc_close((int)sdir);
    if (!ok || n<=0 || (oc_u64)n!=m.size) return 0;
    target[n]=0;
    char *f[3]; oc_u64 deadline=0, now=0;
    if (oc_fields(target,f,3)!=3 || !oc_equal(f[0],"OCUSB1") ||
        !oc_decimal(f[1],&deadline) || !oc_equal(f[2],expect_rev) ||
        !oc_api_uptime_cs(root,&now)) return 0;
    return now<deadline && deadline<=now+12000;
}

static void oc_usb_retain_set(int root, const char *session_dir, int exists, const char *cur_snap) {
    oc_u64 now=0;
    if (!oc_api_uptime_cs(root,&now)) return;
    char ds[24], target[128];
    oc_u64_dec(now+12000,ds);
    if (!oc_join4(target,sizeof target,"OCUSB1|",ds,"|",exists?cur_snap:"-")) return;
    long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    if (sdir>=0) {
        (void)oc_unlink((int)sdir,"admitted");
        (void)oc_symlink(target,(int)sdir,"admitted");
        (void)oc_close((int)sdir);
    }
}

static void oc_usb_retain_clear(const char *session_dir) {
    long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    if (sdir>=0) { (void)oc_unlink((int)sdir,"admitted"); (void)oc_close((int)sdir); }
}

static int oc_status_identity(int data, int ram, char out[384]) {
    out[0]=0;
    if (data<0 || oc_absent_at(data,"record")) {
        if (!oc_join(out,384,out,"record=absent\n")) return 0;
    } else {
        long fd=oc_openat(data,"record",OC_READ,0);
        char dig[65]; OcMeta m={0};
        int ok=fd>=0 && oc_hash_copy((int)fd,-1,4096,dig,&m)==OC_COPY_OK;
        if (fd>=0 && oc_close((int)fd)<0) ok=0;
        if (!ok || !oc_join4(out,384,out,"record=",dig,"\n")) return 0;
    }
    const char *mks[3]={"selected","access-selected","boot-id"};
    for (unsigned i=0; i<3; ++i) {
        if (oc_absent_at(ram,mks[i])) {
            if (!oc_join4(out,384,out,mks[i],"=absent\n",0)) return 0;
            continue;
        }
        OcMeta m={0};
        if (oc_metadata(ram,mks[i],&m)<0) return 0;
        if ((m.mode&OC_TYPE)==0120000) {
            char lnk[128];
            long n=oc_readlink(ram,mks[i],lnk,sizeof lnk-1);
            if (n<=0 || (oc_u64)n!=m.size) return 0;
            lnk[n]=0;
            if (!oc_join4(out,384,out,mks[i],"=link:",lnk) || !oc_join(out,384,out,"\n")) return 0;
        } else if ((m.mode&OC_TYPE)==OC_REGULAR) {
            long fd=oc_openat(ram,mks[i],OC_READ,0);
            char dig[65]; OcMeta fm={0};
            int ok=fd>=0 && oc_hash_copy((int)fd,-1,4096,dig,&fm)==OC_COPY_OK;
            if (fd>=0 && oc_close((int)fd)<0) ok=0;
            if (!ok || !oc_join4(out,384,out,mks[i],"=file:",dig) || !oc_join(out,384,out,"\n")) return 0;
        } else return 0;
    }
    return 1;
}

typedef struct {
    const char *session_dir, *root_path, *ptr_name;
    const char *rev, *op, *arg, *exp, *des;
    int root, ram, lock_fd, data, snaps_fd;
    int is_usb, exists, empty_state, allow_fallback;
    long owner, group;
    char rec_buf[1024], *rec[13];
    char sel_snap[65], settings_pkg[65];
    const char *err;
} OcApiCtx;

static int oc_spawn_reboot(const OcApiCtx *c) {
#ifdef OC_HOST
    (void)c;
    const char *mk=getenv("OC_HOST_REBOOT_MARKER");
    if (mk && *mk) {
        long fd=oc_openat(OC_CWD,mk,OC_WRITE|OC_CREATE|OC_TRUNC,0600);
        if (fd>=0) { (void)oc_write_all((int)fd,"reboot\n",7); (void)oc_close((int)fd); }
    }
    return 1;
#else
    long pid=oc_fork();
    if (pid<0) return 0;
    if (pid!=0) return 1;
    if (c->snaps_fd>=0) (void)oc_close(c->snaps_fd);
    if (c->data>=0) (void)oc_close(c->data);
    if (c->lock_fd>=0) (void)oc_close(c->lock_fd);
    if (c->ram>=0) (void)oc_close(c->ram);
    if (c->root>=0) (void)oc_close(c->root);
    long devnull=oc_openat(OC_CWD,"/dev/null",OC_RW,0);
    if (devnull>=0) {
        (void)oc_dup2((int)devnull,0); (void)oc_dup2((int)devnull,1); (void)oc_dup2((int)devnull,2);
        if (devnull>2) (void)oc_close((int)devnull);
    }
    oc_sleep_ms(2000);
    char *argv[]={"/bin/busybox","timeout","-t","10","/sbin/reboot",0};
    char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin","LC_ALL=C",0};
    (void)oc_execve("/bin/busybox",argv,env);
    oc_exit(127);
    return 0;
#endif
}

static __attribute__((noinline)) int api_err(OcApiCtx *c, const char *e) { c->err=e; return OC_API_ERR; }

static int oc_api_emit_ctx(OcApiCtx *c, int conflict, int removed_now) {
    return oc_api_emit_status_view(c->root,c->root_path,c->data,c->ram,c->session_dir,c->owner,c->group,
                                   c->exists,c->empty_state,c->rec,c->settings_pkg,c->sel_snap,conflict,removed_now);
}

static int oc_api_match_cur(OcApiCtx *c) {
    return oc_targets_match(c->root,c->data,c->rec[5],c->rec[4],c->owner,c->group) &&
        oc_dependencies_match(c->root,c->data,c->rec[5],c->owner,c->group);
}

static void oc_api_run_gc(OcApiCtx *c) {
    char bs_p[512], fd_s[24]; oc_u32_dec((unsigned)c->lock_fd,fd_s);
    if (oc_verify_pkg_boot_select(c->data,c->root_path,c->rec[3],c->owner,c->group,bs_p)==1) {
        char *gc_argv[]={bs_p,"gc",(char *)c->root_path,fd_s,0};
        (void)oc_run_prog(bs_p,gc_argv,-1,0,0,c->lock_fd);
    }
}

static __attribute__((noinline)) int oc_handle_completion(OcApiCtx *c, int is_dismiss_done) {
    if (is_dismiss_done) {
        if (c->is_usb) return api_err(c,oc_session_is_closed(c->session_dir)?"session_closed":"invalid_request");
        if (!oc_equal(c->exp,"-") || !oc_equal(c->des,"-")) return api_err(c,"invalid_request");
    }
    if (c->is_usb || !c->exists) return api_err(c,"completion_unavailable");
    if (!oc_rec_settled(c->rec)) return api_err(c,"operation_pending");
    char cur_boot[37], snap_pkg[65], comp_ver[64];
    if (!oc_equal(c->rec[1],"active") || !oc_equal(c->sel_snap,c->rec[5]) ||
        !oc_read_boot_id(c->ram,c->owner,c->group,cur_boot) || !oc_equal(cur_boot,c->rec[11])) return api_err(c,"completion_unavailable");
    if (!oc_snap_package_only(c->data,c->rec[5],snap_pkg) || !oc_equal(snap_pkg,c->rec[3])) return api_err(c,"invalid_snapshot");
    if (!oc_session_mf_matches(c->session_dir,c->rec[3])) return api_err(c,"session_replaced");
    if (!oc_package_version(c->data,c->rec[3],comp_ver)) return api_err(c,"invalid_version");
    if (!oc_check_session_pointer(c->ram,c->session_dir,c->ptr_name)) return api_err(c,"session_replaced");
    if (!is_dismiss_done) {
        int ready=oc_equal(c->rec[12],"installed");
        if (ready) {
            char *u_argv[]={
                "sh","-c",
                "P=$1; . \"$P/service.sh\"; current_boot_id() { printf '%s\\n' \"$2\"; }; "
                "file() { test -f \"$1\" && test ! -L \"$1\" && test \"$(readlink -f \"$1\")\" = \"$1\"; }; "
                "service_usb_observe",
                "observe",(char *)c->session_dir,cur_boot,0
            };
            (void)oc_run_prog("/bin/sh",u_argv,-1,0,0,-1);
        }
        OcJson j; j_init(&j,api_mem.json,sizeof api_mem.json);
        const char *cv[7]={"1",c->rec[5],c->rec[3],cur_boot,comp_ver,c->rec[12],ready?"1":0};
        j_kvs(&j,"bsssssb","ok\0revision\0package\0boot\0installedVersion\0notice\0completionReady",cv);
        j_raw(&j,"}\n");
        return (j.ok && oc_write_all(1,j.buf,j.at)) ? OC_API_DONE : OC_API_ERR;
    }
    if (!oc_equal(c->rev,c->rec[5]) || !oc_equal(c->rec[12],"installed")) return api_err(c,"stale_state");
    c->rec[12]="-";
    if (!oc_record_write_atomic(c->root,c->data,c->rec,0)) return api_err(c,"record_rename_failed");
    if (!oc_mark_closed(c->session_dir)) return api_err(c,"state_changed");
    return oc_write_all(1,"{\"ok\":true}\n",12) ? OC_API_DONE : OC_API_ERR;
}

static __attribute__((noinline)) int oc_handle_usb_meta(OcApiCtx *c) {
    int installed=0, retained=0, pending=c->empty_state, restart=0;
    const char *mrev="-", *mnotice="-";
    char inst_ver[64], run_ver[64], pkg[65];
    (void)oc_join(inst_ver,sizeof inst_ver,"","-");
    if (c->exists) {
        mrev=c->rec[5]; mnotice=c->rec[12];
        if (oc_rec_settled(c->rec)) {
            if (!oc_snap_package_only(c->data,c->rec[5],pkg)) return api_err(c,"invalid_snapshot");
            if (oc_equal(c->rec[1],"active")) {
                installed=1;
                if (!oc_package_version(c->data,pkg,inst_ver)) return api_err(c,"invalid_version");
                if (!oc_equal(c->sel_snap,c->rec[5])) restart=1;
            } else retained=1;
        } else { pending=1; restart=1; mrev=c->rec[2]; }
    }
    long sfd=oc_openat(OC_CWD,c->session_dir,OC_DIRECTORY,0);
    int vok=sfd>=0 && oc_read_version_file((int)sfd,0,run_ver);
    int closed=sfd>=0 && !oc_absent_at((int)sfd,"closed");
    if (sfd>=0) (void)oc_close((int)sfd);
    if (!vok) return api_err(c,"invalid_version");
    if (!oc_check_session_pointer(c->ram,c->session_dir,c->ptr_name)) return api_err(c,"session_replaced");
    if (closed) return api_err(c,"session_closed");
    OcJson j; j_init(&j,api_mem.json,sizeof api_mem.json);
    const char *uv[10]={"1",mrev,installed?"1":0,retained?"1":0,pending?"1":0,restart?"1":0,
        mnotice,run_ver,inst_ver,0};
    j_kvs(&j,"bsbbbbsssb",
          "ok\0revision\0installed\0retained\0pending\0restart\0notice\0version\0installedVersion\0completionReady",uv);
    j_raw(&j,"}\n");
    return (j.ok && oc_write_all(1,j.buf,j.at)) ? OC_API_DONE : OC_API_ERR;
}

static __attribute__((noinline)) int oc_handle_uninstall(OcApiCtx *c) {
    if (!c->exists) return api_err(c,"not_installed");
    if (oc_equal(c->rec[1],"removed")) {
        if (!oc_uninstall_cleanup(c->root,c->root_path,c->data,c->session_dir,c->owner,c->group,&c->err)) return OC_API_ERR;
        (void)oc_close(c->data); c->data=-1; c->exists=0; c->empty_state=0;
        if (c->is_usb) oc_usb_retain_set(c->root,c->session_dir,0,"-");
        return oc_api_emit_ctx(c,0,1);
    }
    if (!oc_equal(c->rec[1],"active")) return api_err(c,"not_installed");
    if (!oc_api_match_cur(c) || !oc_uninstall_owned(c->data,c->rec[5],c->rec[4],c->owner,c->group)) return api_err(c,"state_changed");
    if (!oc_snap_read(c->data,c->rec[5],&api_snap_a,0,0,0,0,0)) return api_err(c,"invalid_snapshot");
    if (!oc_snap_read(c->data,c->rec[4],&api_snap_b,0,0,0,0,0)) return api_err(c,"originals_changed");
    int bdir=-1, rtmp_fd=-1; char rtmp_leaf[48]; rtmp_leaf[0]=0;
    {
        char bp[128], cp[128];
        if (!oc_join(bp,sizeof bp,"snapshots/",c->rec[4]) || !oc_join(cp,sizeof cp,"snapshots/",c->rec[5])) return api_err(c,"plan_failed");
        bdir=oc_open_private(c->data,bp);
        int cdir=oc_open_private(c->data,cp);
        int cur_has_sel = cdir>=0 && !oc_absent_at(cdir,"selector");
        int base_has_sel = bdir>=0 && !oc_absent_at(bdir,"selector");
        if (cdir>=0) (void)oc_close(cdir);
        if (bdir<0) return api_err(c,"originals_changed");
        if (cur_has_sel && !base_has_sel) {
            char rn[33];
            if (!oc_random(c->root,rn) || !oc_join(rtmp_leaf,sizeof rtmp_leaf,".access-",rn) ||
                oc_mkdir(c->data,rtmp_leaf,0700)<0) { (void)oc_close(bdir); return api_err(c,"selector_plan_failed"); }
            rtmp_fd=oc_open_private(c->data,rtmp_leaf);
            int rok=rtmp_fd>=0 && oc_new_text(rtmp_fd,"selector","-\n",0600);
            if (rok && api_snap_b.has_access) {
                const char *an[3]={"access","runlogin","sshd.conf"};
                for (unsigned i=0; rok && i<3; ++i) rok=oc_copy_file_at(bdir,an[i],rtmp_fd,an[i],0600,1,0,0);
            }
            if (!rok) {
                if (rtmp_fd>=0) (void)oc_close(rtmp_fd);
                oc_cleanup_work(c->data,rtmp_leaf); (void)oc_close(bdir);
                return api_err(c,"selector_plan_failed");
            }
        }
    }
    char after_id[65], prep_nonce[33], before_id[65];
    int sok=oc_join(before_id,sizeof before_id,"",c->rec[5]) &&
        oc_snapshot_create(c->root,c->data,c->rec[4],"-",api_snap_b.prefs.nvram,api_snap_b.prefs.metadata,
                           before_id,rtmp_fd>=0?rtmp_fd:bdir,"",c->session_dir,c->root_path,c->owner,c->group,after_id);
    if (rtmp_fd>=0) { (void)oc_close(rtmp_fd); oc_cleanup_work(c->data,rtmp_leaf); }
    (void)oc_close(bdir);
    if (!sok) return api_err(c,"plan_failed");
    if (!oc_transaction_prepare(c->root,c->data,c->rec,"uninstall",before_id,after_id,c->rec[4],1,c->owner,c->group,prep_nonce))
        return api_err(c,"record_rename_failed");
    c->rec[2]=prep_nonce;
    if (!oc_transaction_reconcile(c->root,c->root_path,c->data,c->rec,c->session_dir,prep_nonce,c->owner,c->group,&c->err)) return OC_API_ERR;
    if (!oc_uninstall_cleanup(c->root,c->root_path,c->data,c->session_dir,c->owner,c->group,&c->err)) return OC_API_ERR;
    (void)oc_close(c->data); c->data=-1; c->exists=0; c->empty_state=0;
    if (c->is_usb) oc_usb_retain_set(c->root,c->session_dir,0,"-");
    return oc_api_emit_ctx(c,0,1);
}

static int oc_commit_set_txn(OcApiCtx *c, const char *before_id, const char *after_id) {
    char prep_nonce[33];
    if (!oc_transaction_prepare(c->root,c->data,c->rec,"set",before_id,after_id,c->rec[4],1,c->owner,c->group,prep_nonce))
        return api_err(c,"record_rename_failed");
    c->rec[2]=prep_nonce;
    if (!oc_transaction_reconcile(c->root,c->root_path,c->data,c->rec,c->session_dir,prep_nonce,c->owner,c->group,&c->err)) return OC_API_ERR;
    if (!oc_record_read_any(c->data,c->owner,c->group,c->rec_buf,sizeof c->rec_buf,c->rec)) return api_err(c,"invalid_record");
    oc_api_run_gc(c);
    return oc_api_emit_ctx(c,0,0);
}

static __attribute__((noinline)) int oc_handle_access(OcApiCtx *c, int is_import) {
    if (!c->exists || !oc_equal(c->rec[1],"active")) return api_err(c,"not_installed");
    char cpkg[65];
    if (c->settings_pkg[0] && (!oc_snap_package_only(c->data,c->rec[5],cpkg) || !oc_equal(cpkg,c->settings_pkg)))
        return api_err(c,"restart_required");
    if (!oc_session_mf_matches(c->session_dir,c->rec[3])) return api_err(c,"session_replaced");
    if (!oc_api_match_cur(c)) return api_err(c,"state_changed");
    if (!oc_snap_read(c->data,c->rec[5],&api_snap_a,0,0,0,1,0) || !api_snap_a.prefs.is_oc2) return api_err(c,"unsupported_snapshot");
    if (!api_snap_a.has_access) return api_err(c,"developer_update_required");
    if (oc_equal(api_snap_a.acc_fields[5],"-")) return api_err(c,"developer_reinstall_required");
    if (!oc_snap_read(c->data,c->rec[4],&api_snap_b,0,0,0,1,0)) return api_err(c,"originals_changed");
    char console_dig[65]; console_dig[0]=0;
    {
        OcManifest pmf;
        int pdir=oc_open_pkg_verified(c->data,api_snap_a.prefs.package,&pmf);
        const char *cd=pdir>=0?oc_digest(&pmf,"console.sh"):0;
        int pok=pdir>=0 && cd && oc_join(console_dig,sizeof console_dig,"",cd) && oc_members(pdir,&pmf,1);
        if (pdir>=0 && oc_close(pdir)<0) pok=0;
        if (!pok) return api_err(c,"state_changed");
    }
    if (!oc_check_active_pins(c->root,c->data,api_snap_a.prefs.package,c->rec[5],
                              api_snap_a.prefs.base,api_snap_a.prefs.touch,&c->err)) return OC_API_ERR;
    char new_uart[4], new_ssh[4], new_key[65];
    if (!oc_join(new_uart,sizeof new_uart,"",api_snap_a.acc_fields[0]) ||
        !oc_join(new_ssh,sizeof new_ssh,"",api_snap_a.acc_fields[1]) ||
        !oc_join(new_key,sizeof new_key,"",api_snap_a.acc_fields[2])) return api_err(c,"access_plan_failed");
    if (is_import) {
        if (!oc_equal(c->arg,"-") || !oc_equal(c->exp,"-") || !oc_equal(c->des,"-")) return api_err(c,"invalid_request");
        const char *kerr="public_key_import_failed";
        if (!oc_access_key_import(c->root,c->root_path,c->data,c->owner,c->group,new_key,&kerr)) return api_err(c,kerr);
    } else {
        if (!oc_bit(c->exp) || !oc_bit(c->des)) return api_err(c,"invalid_setting");
        char *dst=oc_equal(c->arg,"uart")?new_uart:new_ssh;
        if (!oc_equal(dst,c->exp)) return api_err(c,"stale_setting");
        (void)oc_join(dst,4,"",c->des);
    }
    char anonce[33], aleaf[48], orig_cfg[1024];
    if (!oc_random(c->root,anonce) || !oc_join(aleaf,sizeof aleaf,".access-",anonce) ||
        oc_mkdir(c->data,aleaf,0700)<0) return api_err(c,"access_plan_failed");
    int awfd=oc_open_private(c->data,aleaf);
    int aok=awfd>=0 && oc_access_compose(c->root,c->root_path,c->data,c->session_dir,c->rec[4],console_dig,awfd,aleaf,
                                         new_uart,new_ssh,new_key,c->owner,c->group);
    int cfg_ok=0;
    if (aok) {
        char cp[128];
        int cdir=oc_join(cp,sizeof cp,"snapshots/",c->rec[5]) ? oc_open_private(c->data,cp) : -1;
        const char *copy_names[6]={"selector","sm-normal.conf","sm-wcp.conf","index.html","mmui.xml","vui-plugins.list"};
        for (unsigned i=0; aok && cdir>=0 && i<6; ++i) {
            if (oc_absent_at(cdir,copy_names[i])) continue;
            aok=oc_copy_file_at(cdir,copy_names[i],awfd,copy_names[i],0600,1,0,0);
        }
        cfg_ok=aok && cdir>=0 && oc_text(cdir,"config",orig_cfg,sizeof orig_cfg,0)>0;
        if (cdir>=0) (void)oc_close(cdir);
    }
    if (!aok) {
        if (awfd>=0) (void)oc_close(awfd);
        oc_cleanup_work(c->data,aleaf); return api_err(c,"access_plan_failed");
    }
    if (!is_import && oc_equal(c->exp,c->des)) {
        (void)oc_close(awfd); oc_cleanup_work(c->data,aleaf);
        return oc_api_emit_ctx(c,0,0);
    }
    char after_id[65], before_id[65];
    int cok=cfg_ok && oc_join(before_id,sizeof before_id,"",c->rec[5]) &&
        oc_snapshot_create(c->root,c->data,before_id,api_snap_a.prefs.package,api_snap_a.prefs.nvram,
                           api_snap_a.prefs.metadata,before_id,awfd,orig_cfg,c->session_dir,c->root_path,c->owner,c->group,after_id);
    (void)oc_close(awfd); oc_cleanup_work(c->data,aleaf);
    if (!cok) return api_err(c,"plan_failed");
    return oc_commit_set_txn(c,before_id,after_id);
}

static __attribute__((noinline)) int oc_handle_fast_set(OcApiCtx *c) {
    if (!c->exists || !oc_equal(c->rec[1],"active")) return api_err(c,"not_installed");
    char cur_pkg[65];
    if (!oc_snap_package_only(c->data,c->rec[5],cur_pkg) || !oc_equal(cur_pkg,c->settings_pkg)) return api_err(c,"restart_required");
    if (!oc_equal(cur_pkg,c->rec[3]) || !oc_session_mf_matches(c->session_dir,c->rec[3])) return api_err(c,"state_changed");

    char bs_path[512];
    int bs_state=oc_verify_pkg_boot_select(c->data,c->root_path,c->rec[3],c->owner,c->group,bs_path);
    if (bs_state<0) return api_err(c,"state_changed");

    c->snaps_fd=oc_open_private(c->data,"snapshots");
    if (c->snaps_fd<0) return api_err(c,"state_changed");
    int has_plan=-1;
    {
        int sdir=oc_open_private(c->snaps_fd,c->rec[5]);
        char smf[4096]; OcManifest mf;
        if (sdir>=0 && oc_verified_text(sdir,"files.sha256",c->rec[5],smf,sizeof smf) && oc_manifest(smf,&mf,0)) {
            if (oc_digest(&mf,"boot.plan")) {
                OcMeta pm;
                has_plan = (oc_metadata(sdir,"boot.plan",&pm)>=0 && (pm.mode&OC_TYPE)==OC_REGULAR) ? 1 : -1;
            } else has_plan = oc_absent_at(sdir,"boot.plan") ? 0 : -1;
        }
        if (sdir>=0) (void)oc_close(sdir);
    }
    if (has_plan<0 || (bs_state==0 && has_plan==1)) return api_err(c,"state_changed");
    if (bs_state==0 || has_plan==0) {
        if (!c->allow_fallback) return api_err(c,"state_changed");
        (void)oc_unlock(c->lock_fd); return OC_API_FALLBACK;
    }

    OcCatalog cat; cat.count=0;
    if (!oc_snap_read(c->data,c->rec[5],&api_snap_a,&cat,api_mem.cat_buf,sizeof api_mem.cat_buf,0,0) || !api_snap_a.prefs.is_oc2)
        return api_err(c,"state_changed");
    char **slot=0;
    int is_touch=oc_equal(c->arg,"touch");
    if (is_touch) slot=&api_snap_a.prefs.touch;
    else if (oc_equal(c->arg,"warning")) slot=&api_snap_a.prefs.warning;
    else if (oc_equal(c->arg,"base")) slot=&api_snap_a.prefs.base;
    else if (oc_equal(c->arg,"wireless")) slot=&api_snap_a.prefs.wireless;
    else if (oc_equal(c->arg,"carplay-autoshow")) { slot=&api_snap_a.prefs.autoshow; api_snap_a.prefs.has_autoshow=1; }
    else {
        for (unsigned i=0; i<api_snap_a.prefs.svc_count; ++i)
            if (oc_equal(api_snap_a.prefs.svc_ids[i],c->arg)) { slot=&api_snap_a.prefs.svc_vals[i]; break; }
    }
    if (!slot || !(is_touch?(oc_bit(c->exp)||oc_equal(c->exp,"2")):oc_bit(c->exp)) ||
        !(is_touch?(oc_bit(c->des)||oc_equal(c->des,"2")):oc_bit(c->des))) return api_err(c,"invalid_setting");
    if (!oc_equal(*slot,c->exp)) return api_err(c,"stale_setting");

    if (oc_equal(c->exp,c->des)) {
        char *a_argv[]={bs_path,"audit",(char *)c->root_path,c->rec[5],0};
        if (oc_run_prog(bs_path,a_argv,-1,0,0,-1)!=0) return api_err(c,"state_changed");
        return oc_api_emit_ctx(c,0,0);
    }

    if (!oc_snap_read(c->data,c->rec[4],&api_snap_b,0,0,0,0,0)) return api_err(c,"originals_changed");
    const char *old_t=api_snap_a.prefs.touch, *old_w=api_snap_a.prefs.warning, *old_b=api_snap_a.prefs.base;
    const char *old_wl=api_snap_a.prefs.wireless, *old_as=api_snap_a.prefs.autoshow, *cur_nvram=api_snap_a.prefs.nvram;
    int svc_changed = !is_touch && !oc_equal(c->arg,"warning") && !oc_equal(c->arg,"base") &&
        !oc_equal(c->arg,"wireless") && !oc_equal(c->arg,"carplay-autoshow");
    *slot=(char *)c->des;
    const char *new_nvram=oc_equal(api_snap_a.prefs.touch,"1")?"disable":api_snap_b.prefs.nvram;
    api_snap_a.prefs.nvram=(char *)new_nvram;

    int w_chg=!oc_equal(old_w,api_snap_a.prefs.warning), b_chg=!oc_equal(old_b,api_snap_a.prefs.base);
    int wl_chg=!oc_equal(old_wl,api_snap_a.prefs.wireless), as_chg=!oc_equal(old_as,api_snap_a.prefs.autoshow);
    int need_mmui=w_chg||b_chg||svc_changed, need_plugins=b_chg||svc_changed;
    int need_sm=(oc_equal(old_t,"2")!=oc_equal(api_snap_a.prefs.touch,"2"))||w_chg||b_chg||wl_chg||svc_changed;
    int need_index=w_chg||b_chg||svc_changed||as_chg;

    char new_cfg[1024], wnonce[33], work_leaf[48];
    if (!oc_prefs_write(&cat,&api_snap_a.prefs,new_cfg,sizeof new_cfg) ||
        !oc_random(c->root,wnonce) || !oc_join(work_leaf,sizeof work_leaf,".new-",wnonce) ||
        oc_mkdir(c->snaps_fd,work_leaf,0700)<0) return api_err(c,"plan_failed");
    int work_fd=oc_open_private(c->snaps_fd,work_leaf);
    if (work_fd<0 || !oc_new_text(work_fd,"config",new_cfg,0600)) {
        if (work_fd>=0) (void)oc_close(work_fd);
        oc_cleanup_work(c->snaps_fd,work_leaf);
        return api_err(c,"plan_failed");
    }

    int render_ok=1;
    if (need_mmui || need_plugins || need_index) {
        OcManifest pmf;
        int pdir=oc_open_pkg_verified(c->data,c->rec[3],&pmf);
        if (pdir<0) render_ok=0;
        if (render_ok && need_index) {
            char cmf_buf[4096]; OcManifest cmf;
            int cdir=oc_open_composed_verified(c->data,c->rec[3],c->rec[5],cmf_buf,&cmf);
            render_ok=cdir>=0 && oc_render_index_native(pdir,&pmf,cdir,&cmf,work_fd,&api_snap_a.prefs);
            if (cdir>=0) (void)oc_close(cdir);
        }
        if (render_ok && (need_mmui || need_plugins)) {
            const char *nf[4]={"preferences.awk","services.tsv","ui-profile.awk","ui-modules.tsv"};
            for (unsigned i=0; render_ok&&i<4; ++i)
                render_ok=oc_verify_file_sha(pdir,nf[i],oc_digest(&pmf,nf[i]),262144);
            OcMeta cat_m={0};
            long cfd=render_ok?oc_openat(pdir,"services.tsv",OC_READ,0):-1;
            if (cfd<0 || oc_stat((int)cfd,&cat_m)<0) render_ok=0;
            if (cfd>=0) (void)oc_close((int)cfd);
            char dbase[320], cfg_path[320], cfg_len_s[24], cat_len_s[24];
            if (render_ok) {
                oc_u32_dec(oc_length(new_cfg),cfg_len_s); oc_u32_dec((unsigned)cat_m.size,cat_len_s);
                if (!oc_data_base(c->root_path,dbase,sizeof dbase) ||
                    !oc_join4(cfg_path,sizeof cfg_path,dbase,"/snapshots/",work_leaf,"/config")) render_ok=0;
            }
            if (render_ok && need_mmui) {
                int orig=oc_open_private(c->data,"originals");
                int mok=orig>=0 && oc_verify_file_sha(orig,"mmui.xml",
                    oc_pin_digest("originals/mmui.xml","ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0"),262144);
                if (orig>=0) (void)oc_close(orig);
                char mmui_in[320];
                render_ok = mok && oc_join(mmui_in,sizeof mmui_in,dbase,"/originals/mmui.xml") &&
                    oc_run_awk_profile(dbase,c->rec[3],cfg_path,cfg_len_s,cat_len_s,"ui-profile.awk","mmui",mmui_in,work_fd,"mmui.xml");
            }
            if (render_ok && need_plugins)
                render_ok=oc_run_awk_profile(dbase,c->rec[3],cfg_path,cfg_len_s,cat_len_s,"ui-profile.awk","plugins","/dev/null",work_fd,"vui-plugins.list");
        }
        if (pdir>=0) (void)oc_close(pdir);
    }
    if (render_ok && need_sm) {
        char dbase[320], cfg_path[320];
        render_ok=oc_data_base(c->root_path,dbase,sizeof dbase) &&
            oc_join4(cfg_path,sizeof cfg_path,dbase,"/snapshots/",work_leaf,"/config") &&
            oc_render_sm_profiles(c->data,c->root_path,c->rec[3],c->rec[5],cfg_path,oc_length(new_cfg),api_snap_a.prefs.warning,work_fd);
    }
    (void)oc_close(work_fd);
    if (!render_ok) { oc_cleanup_work(c->snaps_fd,work_leaf); return api_err(c,"state_changed"); }

    char rel_work[128], sp_out[128];
    if (!oc_join(rel_work,sizeof rel_work,OC_DATA "/snapshots/",work_leaf)) {
        oc_cleanup_work(c->snaps_fd,work_leaf); return api_err(c,"plan_failed");
    }
    int nv_changed=!oc_equal(cur_nvram,new_nvram);
    char *sp_argv[7]={bs_path,"seal-publish",(char *)c->root_path,c->rec[5],rel_work,nv_changed?(char *)new_nvram:0,0};
    int sp_rc=oc_run_prog(bs_path,sp_argv,-1,sp_out,sizeof sp_out,-1);
    if (sp_rc==95 && !c->allow_fallback && oc_equal(old_t,"2") && !oc_equal(api_snap_a.prefs.touch,"2")) {
        /* Touch=2 -> 0/1 with drifted touch pins: recover natively via full transaction. */
        char sp_leaf[48];
        int ok=oc_join(sp_leaf,sizeof sp_leaf,".sp-",wnonce) && oc_rename(c->snaps_fd,work_leaf,sp_leaf)>=0;
        int wfd=ok?oc_open_private(c->snaps_fd,sp_leaf):-1;
        int cdir=ok?oc_open_private(c->snaps_fd,c->rec[5]):-1;
        if (ok) ok=wfd>=0 && cdir>=0 && oc_api_match_cur(c) &&
            oc_check_active_pins(c->root,c->data,c->rec[3],c->rec[5],
                                 api_snap_a.prefs.base,api_snap_a.prefs.touch,&c->err);
        const char *mems[9]={"access","runlogin","sshd.conf","selector",
            "sm-normal.conf","sm-wcp.conf","index.html","mmui.xml","vui-plugins.list"};
        for (unsigned i=0; ok && i<9; ++i) {
            if (!oc_absent_at(wfd,mems[i]) || oc_absent_at(cdir,mems[i])) continue;
            ok=oc_copy_file_at(cdir,mems[i],wfd,mems[i],0600,1,0,0);
        }
        if (cdir>=0) (void)oc_close(cdir);
        char after_id[65], before_id[65];
        if (ok) ok=oc_join(before_id,sizeof before_id,"",c->rec[5]) &&
            oc_snapshot_create(c->root,c->data,before_id,c->rec[3],new_nvram,api_snap_a.prefs.metadata,
                               before_id,wfd,new_cfg,c->session_dir,c->root_path,c->owner,c->group,after_id);
        if (wfd>=0) (void)oc_close(wfd);
        if (!oc_absent_at(c->snaps_fd,sp_leaf)) oc_cleanup_work(c->snaps_fd,sp_leaf);
        if (!oc_absent_at(c->snaps_fd,work_leaf)) oc_cleanup_work(c->snaps_fd,work_leaf);
        if (!ok) return c->err ? OC_API_ERR : api_err(c,"state_changed");
        return oc_commit_set_txn(c,before_id,after_id);
    }
    if (!oc_absent_at(c->snaps_fd,work_leaf)) oc_cleanup_work(c->snaps_fd,work_leaf);
    if (sp_rc!=0) {
        if (sp_rc==95 && c->allow_fallback) { (void)oc_unlock(c->lock_fd); return OC_API_FALLBACK; }
        return api_err(c,sp_rc==92?"touch_inputs_changed":sp_rc==93?"base_inputs_changed":"state_changed");
    }
    if (!oc_one_line(sp_out) || !oc_hex(sp_out,64)) return api_err(c,"plan_failed");
    {
        int adir=oc_open_private(c->snaps_fd,sp_out);
        char chk_cfg[1024];
        int cok=adir>=0 && oc_text(adir,"config",chk_cfg,sizeof chk_cfg,0)>0 && oc_equal(chk_cfg,new_cfg);
        if (adir>=0) (void)oc_close(adir);
        if (!cok) return api_err(c,"plan_failed");
    }

    if (nv_changed) {
        char *prev_cur=c->rec[5];
        c->rec[1]="set"; c->rec[6]=prev_cur; c->rec[7]=sp_out;
        if (!oc_record_write_atomic(c->root,c->data,c->rec,0)) return api_err(c,"record_rename_failed");
        if (!oc_nvram_change(c->root,cur_nvram,new_nvram)) return api_err(c,"nvram_commit_failed");
        char *au_argv[]={bs_path,"audit",(char *)c->root_path,prev_cur,sp_out,0};
        if (oc_run_prog(bs_path,au_argv,-1,0,0,-1)!=0) return api_err(c,"final_verification_failed");
    }

    char final_nonce[33];
    c->rec[1]="active"; c->rec[5]=sp_out; c->rec[6]="-"; c->rec[7]="-"; c->rec[8]="-";
    c->rec[9]="3"; c->rec[10]="-"; c->rec[11]="-"; c->rec[12]="restart";
    if (!oc_record_write_atomic(c->root,c->data,c->rec,final_nonce)) return api_err(c,"record_rename_failed");
    c->rec[2]=final_nonce;

    oc_api_run_gc(c);
    return oc_api_emit_ctx(c,0,0);
}

static int oc_session_has_file(const char *session_dir, const char *name) {
    long sfd=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    int has=sfd>=0 && !oc_absent_at((int)sfd,name);
    if (sfd>=0) (void)oc_close((int)sfd);
    return has;
}

static int oc_api_handle_dir(const char *session_dir, const char *rev, const char *op,
                             const char *arg, const char *exp, const char *des, int allow_fallback) {
    int has_backend = allow_fallback && oc_session_has_file(session_dir,"backend.sh");
    int op_dm = oc_equal(op,"dismiss"), op_st = oc_equal(op,"status"), op_set = oc_equal(op,"set");
    int arg_dash = oc_equal(arg,"-");
    int is_dismiss_usb = op_dm && oc_equal(arg,"usb");
    int is_dismiss_done = op_dm && arg_dash;
    int is_status_settings = op_st && oc_equal(arg,"settings");
    int is_status_comp = op_st && oc_equal(arg,"completion");
    int is_status_full = op_st && arg_dash;
    int is_restart = arg_dash && oc_equal(op,"restart");
    int is_uninstall = arg_dash && oc_equal(op,"uninstall");
    int is_recover = arg_dash && oc_equal(op,"recover");
    int is_import = arg_dash && oc_equal(op,"import");
    int is_access_set = op_set && (oc_equal(arg,"uart") || oc_equal(arg,"ssh"));
    int is_fast_set = op_set && !is_access_set;
    if (!is_dismiss_usb && !is_dismiss_done && !is_status_settings && !is_status_comp &&
        !is_status_full && !is_restart && !is_uninstall && !is_recover &&
        !is_import && !is_access_set && !is_fast_set)
        return has_backend ? OC_API_FALLBACK : emit_fail("invalid_request");

    static OcApiCtx ctx;
    OcApiCtx *c=&ctx;
    c->session_dir=session_dir; c->root_path=oc_root_path(); c->ptr_name="runtime";
    c->rev=rev; c->op=op; c->arg=arg; c->exp=exp; c->des=des;
    c->root=-1; c->ram=-1; c->lock_fd=-1; c->data=-1; c->snaps_fd=-1;
    c->is_usb=0; c->exists=0; c->empty_state=0; c->allow_fallback=has_backend;
    c->owner=oc_owner(); c->group=oc_group();
    c->sel_snap[0]=0; c->settings_pkg[0]=0; c->err=0;
    int res=has_backend ? OC_API_FALLBACK : OC_API_ERR;

    c->root=(int)oc_openat(OC_CWD,c->root_path,OC_DIRECTORY,0);
    if (c->root<0) { if (!has_backend) c->err="runtime_unavailable"; goto out; }
    c->ram=oc_open_ram_dir(c->root);
    if (c->ram<0) { if (!has_backend) c->err="runtime_unavailable"; goto out; }

    if (!oc_check_session_pointer(c->ram,session_dir,"runtime")) {
        if (!oc_check_session_pointer(c->ram,session_dir,"usb-runtime")) { c->err="session_replaced"; goto out; }
        c->is_usb=1; c->ptr_name="usb-runtime";
    }
    if (c->is_usb && !op_st && !is_dismiss_usb && !is_uninstall && !is_recover && !is_restart) {
        c->err="invalid_request"; goto out;
    }

    char op_tag[96];
    if (!oc_join4(op_tag,sizeof op_tag,c->is_usb?"usb:":"settings:",op,":",arg)) { c->err="invalid_request"; goto out; }
    if (!oc_firmware_guard(c->root,op_tag,oc_big_buf,sizeof oc_big_buf,&c->err)) goto out;

    {
        OcMeta lm;
        long lfd=oc_openat(c->ram,"lock",OC_RW,0);
        if (lfd<0 || oc_stat((int)lfd,&lm)<0 || (lm.mode&OC_TYPE)!=OC_REGULAR ||
            lm.uid!=(unsigned)c->owner || lm.gid!=(unsigned)c->group) {
            if (lfd>=0) (void)oc_close((int)lfd);
            c->err="invalid_lock"; goto out;
        }
        if (is_dismiss_usb) {
            (void)oc_close((int)lfd);
            if (!c->is_usb) { c->err="invalid_request"; goto out; }
            if (!oc_mark_closed(session_dir)) { c->err="state_changed"; goto out; }
            res=oc_write_all(1,"{\"ok\":true}\n",12) ? OC_API_DONE : OC_API_ERR;
            goto out;
        }
        if ((is_status_settings ? oc_lock_sh((int)lfd) : oc_lock((int)lfd)) < 0) {
            (void)oc_close((int)lfd); c->err="busy"; goto out;
        }
        c->lock_fd=(int)lfd;
    }
    if (!oc_check_session_pointer(c->ram,session_dir,c->ptr_name)) { c->err="session_replaced"; goto out; }

    if (!oc_load_state(c->root,c->owner,c->group,&c->data,&c->exists,&c->empty_state,c->rec_buf,c->rec,&c->err)) goto out;
    (void)oc_read_hex64_file(c->ram,"selected",c->sel_snap);

    /* Under-lock USB closed/retained/fence checks (eliminates pre-lock TOCTOU). */
    if (c->is_usb && !op_st && !is_dismiss_usb) {
        if (oc_session_is_closed(session_dir)) {
            const char *expect_rev=0;
            if (c->exists && oc_rec_settled(c->rec)) expect_rev=c->rec[5];
            else if (!c->exists && !c->empty_state) expect_rev="-";
            if (!(is_restart && oc_usb_retained(c->root,session_dir,expect_rev))) {
                c->err="session_closed"; goto out;
            }
        }
        if ((is_uninstall || is_recover) && !oc_absent_at(c->ram,"runtime")) {
            if (has_backend) { (void)oc_unlock(c->lock_fd); res=OC_API_FALLBACK; goto out; }
            c->err="session_replaced"; goto out;
        }
    }

    if (is_status_comp || is_dismiss_done) { res=oc_handle_completion(c,is_dismiss_done); goto out; }
    if (c->is_usb && is_status_settings) { res=oc_handle_usb_meta(c); goto out; }

    if (!c->is_usb && c->exists && !oc_equal(c->rec[1],"purge") && !oc_equal(c->rec[1],"removed")) {
        if (!c->sel_snap[0] || !oc_snap_package_only(c->data,c->sel_snap,c->settings_pkg) || oc_equal(c->settings_pkg,"-")) {
            c->err="invalid_selected_snapshot"; goto out;
        }
    }
    if (is_status_settings) { res=oc_api_emit_ctx(c,0,0); goto out; }

    if (is_status_full) {
        int conflict=0;
        if (c->exists && !oc_equal(c->rec[1],"purge")) {
            char id_before[384], id_after[384];
            if (!oc_status_identity(c->data,c->ram,id_before)) { c->err="state_changed"; goto out; }
            if (oc_unlock(c->lock_fd)<0) { c->err="invalid_lock"; goto out; }
            conflict=!oc_api_match_cur(c);
            if (oc_lock(c->lock_fd)<0) { c->err="busy"; goto out; }
            if (!oc_check_session_pointer(c->ram,session_dir,c->ptr_name)) { c->err="session_replaced"; goto out; }
            if (!oc_status_identity(c->data,c->ram,id_after)) { c->err="state_changed"; goto out; }
            if (!oc_equal(id_before,id_after)) { c->err="busy"; goto out; }
        }
        res=oc_api_emit_ctx(c,conflict,0); goto out;
    }

    if (c->is_usb) oc_usb_retain_clear(session_dir);

    int settled=c->exists && oc_rec_settled(c->rec);
    if (c->exists) {
        if (!oc_equal(rev,settled?c->rec[5]:c->rec[2])) { c->err="stale_state"; goto out; }
        if (!settled) {
            if (!is_recover) { c->err="operation_pending"; goto out; }
            int removed_now=0;
            if (!oc_equal(c->rec[1],"purge")) {
                if (!oc_transaction_reconcile(c->root,c->root_path,c->data,c->rec,session_dir,0,c->owner,c->group,&c->err)) goto out;
                if (!oc_record_read_any(c->data,c->owner,c->group,c->rec_buf,sizeof c->rec_buf,c->rec)) { c->err="invalid_record"; goto out; }
            }
            if (oc_equal(c->rec[1],"removed") || oc_equal(c->rec[1],"purge")) {
                if (!oc_uninstall_cleanup(c->root,c->root_path,c->data,session_dir,c->owner,c->group,&c->err)) goto out;
                (void)oc_close(c->data); c->data=-1; c->exists=0; c->empty_state=0; removed_now=1;
            }
            int conflict=c->exists && !oc_equal(c->rec[1],"purge") && !oc_api_match_cur(c);
            if (c->is_usb) oc_usb_retain_set(c->root,session_dir,c->exists,c->exists?c->rec[5]:"-");
            res=oc_api_emit_ctx(c,conflict,removed_now); goto out;
        }
    } else if (!oc_equal(rev,"-")) {
        c->err="stale_state"; goto out;
    }

    if (is_restart) {
        if (c->exists) { if (!oc_api_match_cur(c)) { c->err="state_changed"; goto out; } }
        else if (!oc_data_absent(c->root)) { c->err="operation_pending"; goto out; }
        if (!oc_mounts_mode(c->root,oc_mscratch,sizeof oc_mscratch,0)) { c->err="root_mount_changed"; goto out; }
        if (c->is_usb) oc_usb_retain_set(c->root,session_dir,c->exists,c->exists?c->rec[5]:"-");
        if (!oc_spawn_reboot(c)) { c->err="restart_failed"; goto out; }
        res=oc_write_all(1,"{\"ok\":true,\"restarting\":true}\n",30) ? OC_API_DONE : OC_API_ERR;
        goto out;
    }
    if (is_recover) {
        int removed_now=0;
        if (!c->exists && c->empty_state) {
            if (!oc_uninstall_cleanup(c->root,c->root_path,c->data,session_dir,c->owner,c->group,&c->err)) goto out;
            (void)oc_close(c->data); c->data=-1; c->empty_state=0; removed_now=1;
        }
        int conflict=c->exists && !oc_equal(c->rec[1],"purge") && !oc_api_match_cur(c);
        if (c->is_usb) oc_usb_retain_set(c->root,session_dir,c->exists,c->exists?c->rec[5]:"-");
        res=oc_api_emit_ctx(c,conflict,removed_now); goto out;
    }
    if (!oc_mounts_mode(c->root,oc_mscratch,sizeof oc_mscratch,0)) { c->err="root_mount_changed"; goto out; }
    if (is_uninstall) { res=oc_handle_uninstall(c); goto out; }
    if (is_import || is_access_set) { res=oc_handle_access(c,is_import); goto out; }
    res=oc_handle_fast_set(c);

out:
    if (c->snaps_fd>=0) (void)oc_close(c->snaps_fd);
    if (c->data>=0) (void)oc_close(c->data);
    if (c->lock_fd>=0) (void)oc_close(c->lock_fd);
    if (c->ram>=0) (void)oc_close(c->ram);
    if (c->root>=0) (void)oc_close(c->root);
    return c->err ? emit_fail(c->err) : res;
}

int oc_api_handle(const char *token_path, const char *rev, const char *op,
                  const char *arg, const char *exp, const char *des) {
    char session_dir[512];
    unsigned tlen=oc_length(token_path);
    if (tlen<7 || !oc_equal(token_path+tlen-6,"/token") || tlen-6>=sizeof session_dir) return OC_API_FALLBACK;
    for (unsigned i=0; i<tlen-6; ++i) session_dir[i]=token_path[i];
    session_dir[tlen-6]=0;
    return oc_api_handle_dir(session_dir,rev,op,arg,exp,des,1);
}

/* ---------- Internal CLI subcommands for backend.sh / service.sh ---------- */
int oc_api_cli(int argc, char **argv) {
    if (oc_equal(argv[1],"--handle") && argc==8) {
        int r=oc_api_handle_dir(argv[2],argv[3],argv[4],argv[5],argv[6],argv[7],0);
        return r==OC_API_DONE ? 0 : 1;
    }
    const char *root_path=oc_root_path();
    long owner=oc_owner(), group=oc_group();
    int root=(int)oc_openat(OC_CWD,root_path,OC_DIRECTORY,0);
    if (root<0) return 1;
    int ram=oc_open_ram_dir(root), rc=64;

    if (oc_equal(argv[1],"--status-view") && argc>=6 && argc<=7) {
        if (ram<0) {
            rc=emit_fail("runtime_unavailable");
        } else {
            const char *session_dir=argv[2];
            int conflict=oc_equal(argv[3],"1")||oc_equal(argv[3],"true");
            int removed_now=oc_equal(argv[4],"1")||oc_equal(argv[4],"true");
            int empty_state=oc_equal(argv[5],"1")||oc_equal(argv[5],"true");
            const char *settings_pkg=(argc==7 && !oc_equal(argv[6],"-"))?argv[6]:"";
            int data=-1, exists=0, tmp_empty=0;
            const char *lerr=0;
            char rec_buf[1024], *rec[13], sel_snap[65]; sel_snap[0]=0;
            (void)oc_read_hex64_file(ram,"selected",sel_snap);
            if (!oc_load_state(root,owner,group,&data,&exists,&tmp_empty,rec_buf,rec,&lerr)) {
                rc=emit_fail(lerr);
            } else {
                rc=oc_api_emit_status_view(root,root_path,data,ram,session_dir,owner,group,
                                           exists,empty_state,rec,settings_pkg,sel_snap,conflict,removed_now);
            }
            if (data>=0) (void)oc_close(data);
        }
    } else if (oc_equal(argv[1],"--gc") && argc==4) {
        int data=oc_open_data_dir(root);
        char bs_path[512]; oc_u64 lfd=0;
        if (data>=0 && oc_decimal(argv[3],&lfd) && lfd>=3 && lfd<=1024 &&
            oc_verify_pkg_boot_select(data,root_path,argv[2],owner,group,bs_path)==1) {
            char *gc_argv[]={bs_path,"gc",(char *)root_path,argv[3],0};
            (void)oc_run_prog(bs_path,gc_argv,-1,0,0,(int)lfd);
        }
        if (data>=0) (void)oc_close(data);
        rc=0;
    } else if (oc_equal(argv[1],"--nvram") && argc>=3) {
        if (oc_equal(argv[2],"read") && argc==3) {
            char nv[16];
            if (oc_nvram_at(root,nv) && oc_write_all(1,nv,oc_length(nv)) && oc_write_all(1,"\n",1)) rc=0;
            else rc=1;
        } else if (oc_equal(argv[2],"change") && argc==5) {
            rc=oc_nvram_change(root,argv[3],argv[4]) ? 0 : 1;
        }
#ifdef OC_HOST
    } else if (oc_equal(argv[1],"--test-root-publish") && argc==13) {
        int data=oc_open_data_dir(root);
        if (data>=0) {
            int ok=oc_root_publish(root,root_path,data,argv[2],argv[3],argv[4],argv[5],argv[6],argv[7],
                                   oc_equal(argv[8],"-")?0:argv[8],oc_equal(argv[9],"-")?0:argv[9],
                                   oc_equal(argv[10],"1"),oc_equal(argv[11],"-")?0:argv[11],owner,group);
            (void)oc_close(data);
            rc=ok?0:1;
        } else rc=1;
    } else if (oc_equal(argv[1],"--test-staging-guard") && argc==2) {
        rc=oc_startup_staging_guard(root) ? 0 : 1;
    } else if (oc_equal(argv[1],"--test-key-import") && argc==2) {
        int data=oc_open_data_dir(root);
        char kid[65]; const char *kerr="import_failed";
        if (data>=0 && oc_access_key_import(root,root_path,data,owner,group,kid,&kerr)) {
            rc=(oc_write_all(1,kid,64) && oc_write_all(1,"\n",1)) ? 0 : 1;
        } else {
            (void)oc_write_all(2,kerr,oc_length(kerr)); (void)oc_write_all(2,"\n",1);
            rc=1;
        }
        if (data>=0) (void)oc_close(data);
#endif
    }
    if (ram>=0) (void)oc_close(ram);
    (void)oc_close(root);
    return rc;
}
