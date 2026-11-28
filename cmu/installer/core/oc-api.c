/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native interactive API handlers for Settings and USB maintenance.
 * Delegates profile rendering to oc-render.c, boot selection/GC to persistent
 * boot-select, and cold USB install to the verified native install binary.
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
    char inst_err[512];
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

static int oc_rec_settled(char **rec) {
    return oc_equal(rec[6],"-") && oc_equal(rec[7],"-") &&
        (oc_equal(rec[1],"active") || oc_equal(rec[1],"removed"));
}
static int oc_session_is_closed(const char *session_dir) {
    long sfd=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    int cl=sfd<0 || !oc_absent_at((int)sfd,"closed");
    if (sfd>=0) (void)oc_close((int)sfd);
    return cl;
}

static int emit_fail(const char *err) {
    OcJson j; j_init(&j,api_mem.json,sizeof api_mem.json);
    j_kv_bool(&j,"ok",0); j_kv_str(&j,"error",err); j_raw(&j,"}\n");
    if (j.ok) (void)oc_write_all(1,j.buf,j.at);
    return OC_API_ERR;
}

/* ---------- Filesystem / identity helpers ---------- */
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

static int oc_package_version(int data, const char *pkg_id, char out[64]) {
    OcManifest mf;
    int pdir=oc_open_pkg_verified(data,pkg_id,api_mem.mf_buf,sizeof api_mem.mf_buf,&mf);
    if (pdir<0) return 0;
    const char *vd=oc_digest(&mf,"VERSION");
    int ok=vd && oc_read_version_file(pdir,vd,out);
    if (oc_close(pdir)<0) ok=0;
    return ok;
}

static int oc_load_package_catalog(int data, const char *pkg_id, char *buf, unsigned cap, OcCatalog *cat) {
    OcManifest mf;
    int pdir=oc_open_pkg_verified(data,pkg_id,api_mem.mf_buf,sizeof api_mem.mf_buf,&mf);
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
    int sdir=oc_open_sub(data,"snapshots",snap_id);
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
    if (oc_run_cmd(prog,argv,-1,raw,sizeof raw,-1)!=0) return 0;
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

/* ---------- Status view JSON renderer ---------- */
static int oc_api_emit_status_view(int root, const char *root_path, int data, int ram,
                                   const char *session_dir, long owner, long group,
                                   int exists, int empty_state, char *rec[13],
                                   const char *settings_pkg, const char *sel_snap,
                                   int conflict, int removed_now) {
    int installed=0, retained=0, restart=removed_now, pending=empty_state, restart_fixed=0;
    int developer=0, uart_cur=0, ssh_cur=0, wl_cur=0, as_cur=0, has_as=0, so_cur=0, has_so=0, ml_cur=0, has_ml=0, hs_cur=0, has_hs=0, has_oc2=0;
    int has_touch_cur=0, has_base_cur=0, has_pandora=0, has_base=0, has_wl=0;
    const char *rev="-", *notice="-", *touch="0", *warning="0", *uart="0", *owner_ssh="0";
    const char *key="-", *pandora="", *base="", *wireless="", *autoshow="", *source_order="", *menu_loop="", *hold_scroll="";
    const char *touch_cur="", *warning_cur="", *base_cur="", *sel_key="-";
    char inst_ver[64], run_ver[64], fp[128], acc_sel[65];
    int has_acc_sel=oc_read_owned_hex64(ram,"access-selected",owner,group,0,acc_sel)==1;
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
                if (v_snap.prefs.has_source_order) { source_order=v_snap.prefs.source_order; has_so=1; }
                if (v_snap.prefs.has_menu_loop) { menu_loop=v_snap.prefs.menu_loop; has_ml=1; }
                if (v_snap.prefs.has_hold_scroll) { hold_scroll=v_snap.prefs.hold_scroll; has_hs=1; }
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
                s_snap_loaded=1; sel_wl=oc_equal(v_snap.prefs.wireless,"1");
                as_cur=oc_equal(v_snap.prefs.autoshow,"1"); so_cur=oc_equal(v_snap.prefs.source_order,"1");
                ml_cur=oc_equal(v_snap.prefs.menu_loop,"1"); hs_cur=oc_equal(v_snap.prefs.hold_scroll,"1");
                touch_cur=touch; warning_cur=warning; base_cur=base; has_touch_cur=1; if (has_base) has_base_cur=1;
            } else if (sel_snap && *sel_snap && oc_snap_read(data,sel_snap,s_snap,0,0,0,1,settings_pkg)) {
                s_snap_loaded=2; sel_wl=oc_equal(s_snap->prefs.wireless,"1");
                as_cur=oc_equal(s_snap->prefs.autoshow,"1"); so_cur=oc_equal(s_snap->prefs.source_order,"1");
                ml_cur=oc_equal(s_snap->prefs.menu_loop,"1"); hs_cur=oc_equal(s_snap->prefs.hold_scroll,"1");
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
    if (has_so && (oc_equal(source_order,"1")?1:0)!=so_cur) restart=1;
    if (has_ml && (oc_equal(menu_loop,"1")?1:0)!=ml_cur) restart=1;
    if (has_hs && (oc_equal(hold_scroll,"1")?1:0)!=hs_cur) restart=1;

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
            const char *sv[6]={cat.rows[i].id,cat.rows[i].label,v_snap.prefs.svc_vals[i],
                cur_val,cat.rows[i].enable,cat.rows[i].disable};
            j_kvs(&j,"ssrrss","id\0label\0saved\0current\0enable\0disable",sv);
            j_raw(&j,"}");
        }
        j_raw(&j,"]");
    }
    if (has_as) {
        j_kv_raw(&j,"carplayAutoshow",autoshow);
        j_kv_raw(&j,"carplayAutoshowCurrent",as_cur?"1":"0");
    }
    if (has_so) {
        j_kv_raw(&j,"sourceOrder",source_order);
        j_kv_raw(&j,"sourceOrderCurrent",so_cur?"1":"0");
    }
    if (has_ml) {
        j_kv_raw(&j,"menuLoop",menu_loop);
        j_kv_raw(&j,"menuLoopCurrent",ml_cur?"1":"0");
    }
    if (has_hs) {
        j_kv_raw(&j,"holdScroll",hold_scroll);
        j_kv_raw(&j,"holdScrollCurrent",hs_cur?"1":"0");
    }
    j_kv_bool(&j,"completionReady",0);
    j_raw(&j,"}\n");
    return (j.ok && oc_write_all(1,j.buf,j.at)) ? OC_API_DONE : emit_fail("state_changed");
}

/* ---------- Session pointer / close markers ---------- */
static int oc_check_session_pointer(int ram, const char *session_dir, const char *ptr_name, long owner, long group) {
    char link[512];
    return oc_readlink_owned(ram,ptr_name,owner,group,link,sizeof link)>0 && oc_equal(link,session_dir);
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
    while (*p>='0'&&*p<='9') {
        unsigned d=(unsigned)(*p-'0');
        if (sec > 18446744073709551ULL || (sec == 18446744073709551ULL && d > 5)) return 0;
        sec=sec*10+d; ++p;
    }
    if (*p=='.') {
        ++p;
        if (*p<'0'||*p>'9') return 0;
        while (*p>='0'&&*p<='9') {
            if (fd<2) { frac=frac*10+(unsigned)(*p-'0'); ++fd; }
            ++p;
        }
        while (fd<2) { frac*=10; ++fd; }
    }
    if (*p && *p!=' ' && *p!='\t' && *p!='\n') return 0;
    *out_cs=sec*100+frac;
    return 1;
}

static int oc_usb_retained(int root, const char *session_dir, const char *expect_rev, long owner, long group) {
    if (!expect_rev) return 0;
    long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    if (sdir<0) return 0;
    char target[128];
    long n=oc_readlink_owned((int)sdir,"admitted",owner,group,target,sizeof target);
    (void)oc_close((int)sdir);
    if (n<=0) return 0;
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
    int is_usb, exists, empty_state;
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
        oc_dependencies_match(c->root,c->data,c->rec[5]);
}

static void oc_api_run_gc(OcApiCtx *c) {
    char bs_p[512], fd_s[24]; oc_u64_dec((oc_u64)(unsigned)c->lock_fd,fd_s);
    if (oc_pkg_boot_select(c->data,c->root_path,c->rec[3],c->owner,c->group,bs_p)==1) {
        char *gc_argv[]={bs_p,"gc",(char *)c->root_path,fd_s,0};
        (void)oc_run_cmd(bs_p,gc_argv,-1,0,0,c->lock_fd);
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
    if (!oc_check_session_pointer(c->ram,c->session_dir,c->ptr_name,c->owner,c->group)) return api_err(c,"session_replaced");
    if (!is_dismiss_done) {
        int ready=oc_equal(c->rec[12],"installed");
        if (ready) {
            char *u_argv[]={
                "sh","-c",
                "P=$1; B=$2; . \"$P/service.sh\"; current_boot_id() { printf '%s\\n' \"$B\"; }; service_usb_observe",
                "observe",(char *)c->session_dir,cur_boot,0
            };
            (void)oc_run_cmd("/bin/sh",u_argv,-1,0,0,-1);
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
    return oc_write_all(1,"{\"ok\":true}\n",12) ? OC_API_DONE : OC_API_ERR;
}

static __attribute__((noinline)) int oc_handle_usb_meta(OcApiCtx *c) {
    int installed=0, retained=0, pending=c->empty_state, restart=c->empty_state;
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
            } else {
                retained=1;
                if (!oc_absent_at(c->ram,"selected")) restart=1;
            }
        } else { pending=1; restart=1; mrev=c->rec[2]; }
    } else if (!oc_absent_at(c->ram,"selected")) {
        restart=1;
    }
    long sfd=oc_openat(OC_CWD,c->session_dir,OC_DIRECTORY,0);
    int vok=sfd>=0 && oc_read_version_file((int)sfd,0,run_ver);
    int closed=sfd<0 || !oc_absent_at((int)sfd,"closed");
    if (sfd>=0) (void)oc_close((int)sfd);
    if (!vok) return api_err(c,"invalid_version");
    if (!oc_check_session_pointer(c->ram,c->session_dir,c->ptr_name,c->owner,c->group)) return api_err(c,"session_replaced");
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
    if (!oc_api_match_cur(c) || !oc_uninstall_owned(c->data,c->rec[5],c->rec[4])) return api_err(c,"state_changed");
    if (!oc_snap_read(c->data,c->rec[5],&api_snap_a,0,0,0,0,0)) return api_err(c,"invalid_snapshot");
    if (!oc_snap_read(c->data,c->rec[4],&api_snap_b,0,0,0,0,0)) return api_err(c,"originals_changed");
    int bdir=-1, rtmp_fd=-1; char rtmp_leaf[48]; rtmp_leaf[0]=0;
    {
        bdir=oc_open_sub(c->data,"snapshots",c->rec[4]);
        int cdir=oc_open_sub(c->data,"snapshots",c->rec[5]);
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
            if (rok && api_snap_b.has_access) rok=oc_copy_opt(bdir,rtmp_fd,0x007,2);
            if (!rok) {
                if (rtmp_fd>=0) (void)oc_close(rtmp_fd);
                oc_rm_subdir(c->data,rtmp_leaf); (void)oc_close(bdir);
                return api_err(c,"selector_plan_failed");
            }
        }
    }
    char after_id[65], prep_nonce[33], before_id[65];
    int sok=oc_join(before_id,sizeof before_id,"",c->rec[5]) &&
        oc_snapshot_create(c->root,c->data,c->rec[4],"-",api_snap_b.prefs.nvram,api_snap_b.prefs.metadata,
                           before_id,rtmp_fd>=0?rtmp_fd:bdir,"",after_id);
    if (rtmp_fd>=0) { (void)oc_close(rtmp_fd); oc_rm_subdir(c->data,rtmp_leaf); }
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
        int pdir=oc_open_pkg_verified(c->data,api_snap_a.prefs.package,api_mem.mf_buf,sizeof api_mem.mf_buf,&pmf);
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
        if (oc_equal(new_key,api_snap_a.acc_fields[2])) return oc_api_emit_ctx(c,0,0);
    } else {
        if (!oc_bit(c->exp) || !oc_bit(c->des)) return api_err(c,"invalid_setting");
        char *dst=oc_equal(c->arg,"uart")?new_uart:new_ssh;
        if (!oc_equal(dst,c->exp)) return api_err(c,"stale_setting");
        if (oc_equal(c->exp,c->des)) return oc_api_emit_ctx(c,0,0);
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
        int cdir=oc_open_sub(c->data,"snapshots",c->rec[5]);
        aok=cdir>=0 && oc_copy_opt(cdir,awfd,0x1f8,0);
        cfg_ok=aok && oc_text(cdir,"config",orig_cfg,sizeof orig_cfg,0)>0;
        if (cdir>=0) (void)oc_close(cdir);
    }
    if (!aok) {
        if (awfd>=0) (void)oc_close(awfd);
        oc_rm_subdir(c->data,aleaf); return api_err(c,"access_plan_failed");
    }
    char after_id[65], before_id[65];
    int cok=cfg_ok && oc_join(before_id,sizeof before_id,"",c->rec[5]) &&
        oc_snapshot_create(c->root,c->data,before_id,api_snap_a.prefs.package,api_snap_a.prefs.nvram,
                           api_snap_a.prefs.metadata,before_id,awfd,orig_cfg,after_id);
    (void)oc_close(awfd); oc_rm_subdir(c->data,aleaf);
    if (!cok) return api_err(c,"plan_failed");
    return oc_commit_set_txn(c,before_id,after_id);
}

static int oc_prepare_prefs_ctx(OcApiCtx *c, char bs_path[512], OcCatalog *cat) {
    if (!c->exists || !oc_equal(c->rec[1],"active")) return api_err(c,"not_installed");
    char cur_pkg[65];
    if (!oc_snap_package_only(c->data,c->rec[5],cur_pkg) || !oc_equal(cur_pkg,c->settings_pkg)) return api_err(c,"restart_required");
    if (!oc_equal(cur_pkg,c->rec[3]) || !oc_session_mf_matches(c->session_dir,c->rec[3])) return api_err(c,"state_changed");

    if (bs_path) {
        int bs_state=oc_pkg_boot_select(c->data,c->root_path,c->rec[3],c->owner,c->group,bs_path);
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
        if (has_plan!=1 || bs_state!=1) return api_err(c,"state_changed");
    }
    cat->count=0;
    if (!oc_snap_read(c->data,c->rec[5],&api_snap_a,cat,api_mem.cat_buf,sizeof api_mem.cat_buf,0,0) || !api_snap_a.prefs.is_oc2)
        return api_err(c,"state_changed");
    return OC_API_DONE;
}

static __attribute__((noinline)) int oc_apply_prefs_change(
    OcApiCtx *c, const char *bs_path, const OcCatalog *cat,
    const char *old_t, const char *old_w, const char *old_b, const char *old_wl,
    const char *old_as, const char *old_so, const char *old_ml, const char *old_hs,
    const char *cur_nvram, int svc_changed) {
    if (!oc_snap_read(c->data,c->rec[4],&api_snap_b,0,0,0,0,0)) return api_err(c,"originals_changed");
    const char *new_nvram=oc_equal(api_snap_a.prefs.touch,"1")?"disable":api_snap_b.prefs.nvram;
    api_snap_a.prefs.nvram=(char *)new_nvram;

    int w_chg=!oc_equal(old_w,api_snap_a.prefs.warning), b_chg=!oc_equal(old_b,api_snap_a.prefs.base);
    int wl_chg=!oc_equal(old_wl,api_snap_a.prefs.wireless), as_chg=!oc_equal(old_as,api_snap_a.prefs.autoshow);
    if (wl_chg && oc_equal(api_snap_a.prefs.wireless,"1")) {
        int fw=oc_factory_wireless(c->root,c->root_path);
        if (fw!=1) return api_err(c,fw==0?"wireless_factory_enabled":"wireless_unavailable");
    }
    int so_chg=!oc_equal(old_so,api_snap_a.prefs.source_order);
    int ml_chg=!oc_equal(old_ml,api_snap_a.prefs.menu_loop), hs_chg=!oc_equal(old_hs,api_snap_a.prefs.hold_scroll);
    int need_mmui=w_chg||b_chg||svc_changed, need_plugins=b_chg||svc_changed;
    int need_sm=(oc_equal(old_t,"2")!=oc_equal(api_snap_a.prefs.touch,"2"))||w_chg||b_chg||wl_chg||svc_changed;
    int need_index=w_chg||b_chg||svc_changed||as_chg||so_chg||ml_chg||hs_chg;

    char new_cfg[1024], wnonce[33], work_leaf[48];
    if (!oc_prefs_write(cat,&api_snap_a.prefs,new_cfg,sizeof new_cfg) ||
        !oc_random(c->root,wnonce) || !oc_join(work_leaf,sizeof work_leaf,".new-",wnonce) ||
        oc_mkdir(c->snaps_fd,work_leaf,0700)<0) return api_err(c,"plan_failed");
    int work_fd=oc_open_private(c->snaps_fd,work_leaf);
    if (work_fd<0 || !oc_new_text(work_fd,"config",new_cfg,0600)) {
        if (work_fd>=0) (void)oc_close(work_fd);
        oc_rm_subdir(c->snaps_fd,work_leaf);
        return api_err(c,"plan_failed");
    }

    int render_ok=1;
    if (need_index) {
        OcManifest pmf, cmf; char cmf_buf[4096];
        int pdir=oc_open_pkg_verified(c->data,c->rec[3],api_mem.mf_buf,sizeof api_mem.mf_buf,&pmf);
        int cdir=pdir>=0?oc_open_composed_verified(c->data,c->rec[3],c->rec[5],cmf_buf,&cmf):-1;
        render_ok=pdir>=0 && cdir>=0 && oc_render_index_native(pdir,&pmf,cdir,&cmf,work_fd,&api_snap_a.prefs);
        if (cdir>=0) (void)oc_close(cdir);
        if (pdir>=0) (void)oc_close(pdir);
    }
    if (render_ok && (need_mmui || need_plugins || need_sm)) {
        char dbase[320], cfg_path[320];
        render_ok=oc_data_base(c->root_path,dbase,sizeof dbase) &&
            oc_join4(cfg_path,sizeof cfg_path,dbase,"/snapshots/",work_leaf,"/config");
        if (render_ok && (need_mmui || need_plugins))
            render_ok=oc_render_ui_profiles(c->data,c->root_path,c->rec[3],cfg_path,oc_length(new_cfg),need_mmui,need_plugins,work_fd);
        if (render_ok && need_sm)
            render_ok=oc_render_sm_profiles(c->data,c->root_path,c->rec[3],c->rec[5],cfg_path,oc_length(new_cfg),api_snap_a.prefs.warning,work_fd);
    }
    (void)oc_close(work_fd);
    if (!render_ok) { oc_rm_subdir(c->snaps_fd,work_leaf); return api_err(c,"state_changed"); }

    char rel_work[128], sp_out[128];
    if (!oc_join(rel_work,sizeof rel_work,OC_DATA "/snapshots/",work_leaf)) {
        oc_rm_subdir(c->snaps_fd,work_leaf); return api_err(c,"plan_failed");
    }
    int nv_changed=!oc_equal(cur_nvram,new_nvram);
    char *sp_argv[7]={(char *)bs_path,"seal-publish",(char *)c->root_path,c->rec[5],rel_work,nv_changed?(char *)new_nvram:0,0};
    int sp_rc=oc_run_cmd(bs_path,sp_argv,-1,sp_out,sizeof sp_out,-1);
    if (sp_rc==95 && oc_equal(old_t,"2") && !oc_equal(api_snap_a.prefs.touch,"2")) {
        /* Touch=2 -> 0/1 with drifted touch pins: recover natively via full transaction. */
        char sp_leaf[48];
        int ok=oc_join(sp_leaf,sizeof sp_leaf,".sp-",wnonce) && oc_rename(c->snaps_fd,work_leaf,sp_leaf)>=0;
        int wfd=ok?oc_open_private(c->snaps_fd,sp_leaf):-1;
        int cdir=ok?oc_open_private(c->snaps_fd,c->rec[5]):-1;
        if (ok) ok=wfd>=0 && cdir>=0 && oc_api_match_cur(c) && oc_copy_opt(cdir,wfd,0x1ff,1);
        if (cdir>=0) (void)oc_close(cdir);
        char after_id[65], before_id[65];
        if (ok) ok=oc_join(before_id,sizeof before_id,"",c->rec[5]) &&
            oc_snapshot_create(c->root,c->data,before_id,c->rec[3],new_nvram,api_snap_a.prefs.metadata,
                               before_id,wfd,new_cfg,after_id);
        if (wfd>=0) (void)oc_close(wfd);
        if (!oc_absent_at(c->snaps_fd,sp_leaf)) oc_rm_subdir(c->snaps_fd,sp_leaf);
        if (!oc_absent_at(c->snaps_fd,work_leaf)) oc_rm_subdir(c->snaps_fd,work_leaf);
        if (ok && (oc_equal(api_snap_a.prefs.base,"1") || oc_equal(api_snap_a.prefs.touch,"2")))
            ok=oc_check_active_pins(c->root,c->data,c->rec[3],after_id,
                                    api_snap_a.prefs.base,api_snap_a.prefs.touch,&c->err);
        if (!ok) return c->err ? OC_API_ERR : api_err(c,"state_changed");
        return oc_commit_set_txn(c,before_id,after_id);
    }
    if (!oc_absent_at(c->snaps_fd,work_leaf)) oc_rm_subdir(c->snaps_fd,work_leaf);
    if (sp_rc!=0) return api_err(c,sp_rc==92?"touch_inputs_changed":sp_rc==93?"base_inputs_changed":"state_changed");
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
        char *au_argv[]={(char *)bs_path,"audit",(char *)c->root_path,prev_cur,sp_out,0};
        if (oc_run_cmd(bs_path,au_argv,-1,0,0,-1)!=0) return api_err(c,"final_verification_failed");
    }

    char final_nonce[33];
    c->rec[1]="active"; c->rec[5]=sp_out; c->rec[6]="-"; c->rec[7]="-"; c->rec[8]="-";
    c->rec[9]="3"; c->rec[10]="-"; c->rec[11]="-"; c->rec[12]="restart";
    if (!oc_record_write_atomic(c->root,c->data,c->rec,final_nonce)) return api_err(c,"record_rename_failed");
    c->rec[2]=final_nonce;

    oc_api_run_gc(c);
    return oc_api_emit_ctx(c,0,0);
}

static __attribute__((noinline)) int oc_handle_fast_set(OcApiCtx *c) {
    char bs_path[512]; OcCatalog cat;
    if (oc_prepare_prefs_ctx(c,bs_path,&cat)!=OC_API_DONE) return OC_API_ERR;
    char **slot=0;
    int is_touch=oc_equal(c->arg,"touch");
    if (is_touch) slot=&api_snap_a.prefs.touch;
    else if (oc_equal(c->arg,"warning")) slot=&api_snap_a.prefs.warning;
    else if (oc_equal(c->arg,"base")) slot=&api_snap_a.prefs.base;
    else if (oc_equal(c->arg,"wireless")) slot=&api_snap_a.prefs.wireless;
    else if (oc_equal(c->arg,"carplay-autoshow")) { slot=&api_snap_a.prefs.autoshow; api_snap_a.prefs.has_autoshow=1; }
    else if (oc_equal(c->arg,"source-order")) { slot=&api_snap_a.prefs.source_order; api_snap_a.prefs.has_source_order=1; }
    else if (oc_equal(c->arg,"menu-loop")) { slot=&api_snap_a.prefs.menu_loop; api_snap_a.prefs.has_menu_loop=1; }
    else if (oc_equal(c->arg,"hold-scroll")) { slot=&api_snap_a.prefs.hold_scroll; api_snap_a.prefs.has_hold_scroll=1; }
    else {
        for (unsigned i=0; i<api_snap_a.prefs.svc_count; ++i)
            if (oc_equal(api_snap_a.prefs.svc_ids[i],c->arg)) { slot=&api_snap_a.prefs.svc_vals[i]; break; }
    }
    if (!slot || !(is_touch?(oc_bit(c->exp)||oc_equal(c->exp,"2")):oc_bit(c->exp)) ||
        !(is_touch?(oc_bit(c->des)||oc_equal(c->des,"2")):oc_bit(c->des))) return api_err(c,"invalid_setting");
    if (!oc_equal(*slot,c->exp)) return api_err(c,"stale_setting");

    if (oc_equal(c->exp,c->des)) {
        char *a_argv[]={bs_path,"audit",(char *)c->root_path,c->rec[5],0};
        if (oc_run_cmd(bs_path,a_argv,-1,0,0,-1)!=0) return api_err(c,"state_changed");
        return oc_api_emit_ctx(c,0,0);
    }
    const char *old_t=api_snap_a.prefs.touch, *old_w=api_snap_a.prefs.warning, *old_b=api_snap_a.prefs.base;
    const char *old_wl=api_snap_a.prefs.wireless, *old_as=api_snap_a.prefs.autoshow;
    const char *old_so=api_snap_a.prefs.source_order, *old_ml=api_snap_a.prefs.menu_loop;
    const char *old_hs=api_snap_a.prefs.hold_scroll, *cur_nvram=api_snap_a.prefs.nvram;
    int svc_changed = !is_touch && !oc_equal(c->arg,"warning") && !oc_equal(c->arg,"base") &&
        !oc_equal(c->arg,"wireless") && !oc_equal(c->arg,"carplay-autoshow") && !oc_equal(c->arg,"source-order") &&
        !oc_equal(c->arg,"menu-loop") && !oc_equal(c->arg,"hold-scroll");
    *slot=(char *)c->des;
    return oc_apply_prefs_change(c,bs_path,&cat,old_t,old_w,old_b,old_wl,old_as,old_so,old_ml,old_hs,cur_nvram,svc_changed);
}

static __attribute__((noinline)) int oc_handle_export_prefs(OcApiCtx *c) {
    if (!oc_equal(c->exp,"-") || !oc_equal(c->des,"-")) return api_err(c,"invalid_request");
    OcCatalog cat;
    if (oc_prepare_prefs_ctx(c,0,&cat)!=OC_API_DONE) return OC_API_ERR;
    char out[1024];
    if (!oc_prefs_preset_write(&cat,&api_snap_a.prefs,out,sizeof out)) return api_err(c,"export_failed");

    static const char *const vnames[4]={"sda1","sdb1","sdc1","sdd1"};
    long mnt=oc_beneath(c->root,"tmp/mnt",OC_DIRECTORY,0);
    if (mnt<0) return api_err(c,"usb_not_found");
    int found=-1, was_ro=0; char mnt_path[32]; mnt_path[0]=0;
    for (unsigned i=0; i<4; ++i) {
        if (oc_absent_at((int)mnt,vnames[i])) continue;
        char vabs[32];
        if (!oc_join(vabs,sizeof vabs,"/tmp/mnt/",vnames[i])) continue;
        int mode=oc_vfat_mount_mode(c->root,vabs);
        if (!mode) continue;
        long vd=oc_openat((int)mnt,vnames[i],OC_DIRECTORY,0);
        if (vd<0) continue;
        if (found>=0) { (void)oc_close((int)vd); (void)oc_close(found); (void)oc_close((int)mnt); return api_err(c,"multiple_usb_volumes"); }
        found=(int)vd; was_ro=(mode==2);
        (void)oc_join(mnt_path,sizeof mnt_path,vabs,"");
    }
    (void)oc_close((int)mnt);
    if (found<0) return api_err(c,"usb_not_found");
    {
        static const char *const enames[2]={"open-connect.prefs","open-connect.prefs.tmp"};
        for (unsigned i=0; i<2; ++i) {
            OcMeta em={0};
            if (!oc_absent_at(found,enames[i]) &&
                (oc_metadata(found,enames[i],&em)<0 || (em.mode&OC_TYPE)!=OC_REGULAR)) {
                (void)oc_close(found);
                return api_err(c,"export_failed");
            }
        }
    }

    int remounted=0;
    if (was_ro) {
        if (!oc_usb_remount(c->root,mnt_path,1)) { (void)oc_close(found); return api_err(c,"export_failed"); }
        remounted=1;
    }
    long pfd=oc_openat(found,"open-connect.prefs.tmp",OC_WRITE|OC_CREATE|OC_TRUNC,0600);
    OcMeta pm={0};
    int ok=pfd>=0 && oc_stat((int)pfd,&pm)>=0 && (pm.mode&OC_TYPE)==OC_REGULAR &&
        oc_write_all((int)pfd,out,oc_length(out)) && oc_sync((int)pfd)>=0;
    if (pfd>=0 && oc_close((int)pfd)<0) ok=0;
    if (ok && oc_rename(found,"open-connect.prefs.tmp","open-connect.prefs")<0) ok=0;
    if (!ok && pfd>=0) (void)oc_unlink(found,"open-connect.prefs.tmp");
    if (ok && oc_sync(found)<0) ok=0;
    (void)oc_close(found);
    if (remounted && !oc_usb_remount(c->root,mnt_path,0)) ok=0;
    return ok ? oc_api_emit_ctx(c,0,0) : api_err(c,"export_failed");
}

static __attribute__((noinline)) int oc_handle_import_prefs(OcApiCtx *c) {
    if (!oc_equal(c->exp,"-") || !oc_equal(c->des,"-")) return api_err(c,"invalid_request");
    char bs_path[512]; OcCatalog cat;
    if (oc_prepare_prefs_ctx(c,bs_path,&cat)!=OC_API_DONE) return OC_API_ERR;

    const char *perr=0;
    int pfd=oc_open_single_usb_file(c->root,"open-connect.prefs",1023,"preferences_not_found",
                                    "multiple_preferences_files","invalid_preferences",
                                    "invalid_preferences_volume",&perr);
    if (pfd<0) return api_err(c,perr);

    char raw[1024];
    int n=oc_text_fd(pfd,raw,sizeof raw);
    if (oc_close(pfd)<0 || n<=0) return api_err(c,"invalid_preferences");

    const char *old_t=api_snap_a.prefs.touch, *old_w=api_snap_a.prefs.warning, *old_b=api_snap_a.prefs.base;
    const char *old_wl=api_snap_a.prefs.wireless, *old_as=api_snap_a.prefs.autoshow;
    const char *old_so=api_snap_a.prefs.source_order, *old_ml=api_snap_a.prefs.menu_loop;
    const char *old_hs=api_snap_a.prefs.hold_scroll, *cur_nvram=api_snap_a.prefs.nvram;
    unsigned chg=0;
    if (!oc_prefs_preset_apply(raw,(unsigned)n,&cat,&api_snap_a.prefs,&chg))
        return api_err(c,"invalid_preferences");
    if (!chg) {
        char *a_argv[]={bs_path,"audit",(char *)c->root_path,c->rec[5],0};
        if (oc_run_cmd(bs_path,a_argv,-1,0,0,-1)!=0) return api_err(c,"state_changed");
        return oc_api_emit_ctx(c,0,0);
    }
    return oc_apply_prefs_change(c,bs_path,&cat,old_t,old_w,old_b,old_wl,old_as,old_so,old_ml,old_hs,cur_nvram,(chg&256u)!=0);
}

/* Native USB fence: verify active pinned Settings session matches boot-selected package. */
static int oc_usb_fence(OcApiCtx *c) {
    if (oc_absent_at(c->ram,"runtime")) return 1;
    OcMeta tm={0}, pm={0}; char target[512], pkg[65];
    if (oc_readlink_owned(c->ram,"runtime",c->owner,c->group,target,sizeof target)<=0) return 0;
    const char *leaf=target;
    for (const char *p=target; *p; ++p) if (*p=='/') leaf=p+1;
    if (!oc_prefix(leaf,"session-") || !oc_key(leaf)) return 0;
    char srel[96];
    int tdir=oc_join(srel,sizeof srel,"sessions/",leaf) ? oc_open_private(c->ram,srel) : -1;
    if (tdir<0) return 0;
    int ok=oc_stat(tdir,&tm)>=0 && oc_metadata(OC_CWD,target,&pm)>=0 &&
        tm.device==pm.device && tm.inode==pm.inode &&
        c->data>=0 && c->sel_snap[0] && oc_snap_package_only(c->data,c->sel_snap,pkg) &&
        !oc_equal(pkg,"-") && oc_verify_file_sha(tdir,"files.sha256",pkg,65536);
    if (ok) {
        OcManifest pmf;
        int pdir=oc_open_pkg_verified(c->data,pkg,api_mem.mf_buf,sizeof api_mem.mf_buf,&pmf);
        const char *ad=pdir>=0?oc_digest(&pmf,"api"):0;
        ok=pdir>=0 && ad && oc_verify_file_sha(pdir,"api",ad,4194304) &&
            oc_verify_file_sha(tdir,"api",ad,4194304);
        /* Refuse unpinned legacy backend.sh sessions (allow native 8-file or pinned marker). */
        if (ok && (!oc_absent_at(tdir,"backend.sh") || oc_digest(&pmf,"backend.sh"))) {
            const char *bd=oc_digest(&pmf,"backend.sh");
            ok=bd && oc_verified_text(pdir,"backend.sh",bd,oc_big_buf,sizeof oc_big_buf) &&
                (oc_absent_at(tdir,"backend.sh") || oc_verify_file_sha(tdir,"backend.sh",bd,262144));
            if (ok) {
                int pinned=0;
                for (const char *p=oc_big_buf; *p; ++p)
                    if ((p==oc_big_buf || p[-1]=='\n') &&
                        oc_prefix(p,"# Open Connect pinned Settings 1") &&
                        (!p[32] || p[32]=='\n')) { pinned=1; break; }
                ok=pinned;
            }
        }
        if (pdir>=0) (void)oc_close(pdir);
    }
    (void)oc_close(tdir);
    return ok;
}

static int oc_session_install_path(const char *session_dir, char inst_path[560]) {
    long sfd=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    OcManifest smf; OcMeta im={0}; char got[65];
    int ok=sfd>=0 && oc_private((int)sfd) &&
        oc_text((int)sfd,"files.sha256",api_mem.mf_buf,sizeof api_mem.mf_buf,0)>0 &&
        oc_manifest(api_mem.mf_buf,&smf,0);
    const char *idig=ok?oc_digest(&smf,"install"):0;
    ok=ok && idig && oc_hash_file_at((int)sfd,"install",got,&im) &&
        im.size<=4194304 && oc_equal(got,idig) &&
        im.mode==(OC_REGULAR|0700) &&
        im.uid==(unsigned)oc_owner() && im.gid==(unsigned)oc_group() &&
        oc_join(inst_path,560,session_dir,"/install");
    if (sfd>=0) (void)oc_close((int)sfd);
    return ok;
}

static __attribute__((noinline)) void oc_api_log_usb_failure(const char *session_dir, const char *op, const char *err) {
    char inst_path[560];
    if (!oc_session_install_path(session_dir,inst_path)) return;
    char *argv[]={
        inst_path,"--log-failure",(char *)session_dir,(char *)op,(char *)err,
        oc_diag.step[0]?oc_diag.step:"-",
        oc_diag.path[0]?oc_diag.path:"-",
        oc_diag.reason[0]?oc_diag.reason:"-",
        oc_diag.expected[0]?oc_diag.expected:"-",
        oc_diag.actual[0]?oc_diag.actual:"-",
        0
    };
    (void)oc_run_cmd(inst_path,argv,-1,0,0,-1);
}

static __attribute__((noinline)) int oc_handle_install(OcApiCtx *c) {
    if (!c->is_usb) return api_err(c,"invalid_request");
    char inst_path[560];
    if (!oc_session_install_path(c->session_dir,inst_path))
        return api_err(c,"incomplete_maintenance_bundle");
    char *argv[]={inst_path,(char *)c->session_dir,0};
    api_mem.inst_err[0]=0;
    int rc=oc_run_cmd(inst_path,argv,-1,api_mem.inst_err,sizeof api_mem.inst_err,-1);
    if (rc!=0) {
        const char *tok="install_failed";
        char *nl=0;
        for (char *p=api_mem.inst_err; *p; ++p) if (*p=='\n') { nl=p; break; }
        if (nl) *nl++=0;
        if (api_mem.inst_err[0]) {
            int valid=1;
            for (const char *p=api_mem.inst_err; *p; ++p)
                if (!((*p>='a'&&*p<='z')||(*p>='0'&&*p<='9')||*p=='_')) { valid=0; break; }
            if (valid) tok=api_mem.inst_err;
        }
        if (nl && oc_prefix(nl,"DIAG|")) {
            char *d=nl+5, *df[5];
            for (char *p=d; *p; ++p) if (*p=='\n') { *p=0; break; }
            if (oc_fields(d,df,5)==5 && !oc_equal(df[0],"-"))
                oc_diag_set(df[0],oc_equal(df[1],"-")?0:df[1],oc_equal(df[2],"-")?0:df[2],
                            oc_equal(df[3],"-")?0:df[3],oc_equal(df[4],"-")?0:df[4]);
        }
        return api_err(c,tok);
    }
    if (c->data>=0) { (void)oc_close(c->data); c->data=-1; }
    if (!oc_load_state(c->root,c->owner,c->group,&c->data,&c->exists,&c->empty_state,c->rec_buf,c->rec,&c->err))
        return OC_API_ERR;
    if (c->exists) oc_api_run_gc(c);
    oc_usb_retain_set(c->root,c->session_dir,c->exists,c->exists?c->rec[5]:"-");
    return oc_api_emit_ctx(c,0,0);
}

enum {
    OP_DM_USB=1, OP_DM_DONE=2, OP_ST_SET=3, OP_ST_COMP=4, OP_ST_FULL=5,
    OP_RESTART=6, OP_UNINSTALL=7, OP_RECOVER=8, OP_IMPORT=9, OP_ACC_SET=10,
    OP_FAST_SET=11, OP_INSTALL=12, OP_EXPORT_PREFS=13, OP_IMPORT_PREFS=14
};

static int oc_api_dispatch(OcApiCtx *c, int kind) {
    const char *session_dir=c->session_dir, *rev=c->rev, *op=c->op, *arg=c->arg;
    int op_st=(kind==OP_ST_SET || kind==OP_ST_COMP || kind==OP_ST_FULL);
    c->root=(int)oc_openat(OC_CWD,c->root_path,OC_DIRECTORY,0);
    if (c->root<0) return api_err(c,"runtime_unavailable");
    c->ram=oc_open_ram_dir(c->root);
    if (c->ram<0) return api_err(c,"runtime_unavailable");

    if (!oc_check_session_pointer(c->ram,session_dir,"runtime",c->owner,c->group)) {
        if (oc_check_session_pointer(c->ram,session_dir,"usb-runtime",c->owner,c->group)) {
            c->is_usb=1; c->ptr_name="usb-runtime";
        } else {
            int held=0;
            if (!oc_session_is_closed(session_dir)) {
                OcMeta lm;
                long lfd=oc_openat(c->ram,"lock",OC_RW,0);
                if (lfd>=0) {
                    if (oc_stat((int)lfd,&lm)>=0 && (lm.mode&OC_TYPE)==OC_REGULAR &&
                        !(lm.mode&0077) && lm.uid==(unsigned)c->owner && lm.gid==(unsigned)c->group)
                        held=oc_lock_held_ex((int)lfd);
                    (void)oc_close((int)lfd);
                }
            }
            return api_err(c, held ? "busy" : "session_replaced");
        }
    }
    if (c->is_usb && !op_st && kind!=OP_DM_USB && kind!=OP_INSTALL &&
        kind!=OP_UNINSTALL && kind!=OP_RECOVER && kind!=OP_RESTART)
        return api_err(c,"invalid_request");

    char op_tag[96];
    if (!oc_join4(op_tag,sizeof op_tag,c->is_usb?"usb:":"settings:",op,":",arg)) return api_err(c,"invalid_request");
    if (!oc_firmware_guard(c->root,op_tag,oc_big_buf,sizeof oc_big_buf,&c->err)) return OC_API_ERR;

    {
        OcMeta lm;
        long lfd=oc_openat(c->ram,"lock",OC_RW,0);
        if (lfd<0 || oc_stat((int)lfd,&lm)<0 || (lm.mode&OC_TYPE)!=OC_REGULAR ||
            (lm.mode&0077) || lm.uid!=(unsigned)c->owner || lm.gid!=(unsigned)c->group) {
            if (lfd>=0) (void)oc_close((int)lfd);
            return api_err(c,"invalid_lock");
        }
        if (kind==OP_DM_USB) {
            (void)oc_close((int)lfd);
            if (!c->is_usb) return api_err(c,"invalid_request");
            if (!oc_mark_closed(session_dir)) return api_err(c,"state_changed");
            return oc_write_all(1,"{\"ok\":true}\n",12) ? OC_API_DONE : OC_API_ERR;
        }
        if ((kind==OP_ST_SET ? oc_lock_sh((int)lfd) : oc_lock((int)lfd)) < 0) {
            (void)oc_close((int)lfd); return api_err(c,"busy");
        }
        c->lock_fd=(int)lfd;
    }
    if (!oc_check_session_pointer(c->ram,session_dir,c->ptr_name,c->owner,c->group)) return api_err(c,"session_replaced");

    if (!oc_load_state(c->root,c->owner,c->group,&c->data,&c->exists,&c->empty_state,c->rec_buf,c->rec,&c->err))
        return OC_API_ERR;
    (void)oc_read_owned_hex64(c->ram,"selected",c->owner,c->group,0,c->sel_snap);

    /* Under-lock USB closed/retained/fence checks. */
    if (c->is_usb && !op_st && kind!=OP_DM_USB) {
        if (oc_session_is_closed(session_dir)) {
            const char *expect_rev=0;
            if (c->exists && oc_rec_settled(c->rec)) expect_rev=c->rec[5];
            else if (!c->exists && !c->empty_state) expect_rev="-";
            if (!(kind==OP_RESTART && oc_usb_retained(c->root,session_dir,expect_rev,c->owner,c->group))) return api_err(c,"session_closed");
        }
        int cleanup_recover=kind==OP_RECOVER && ((!c->exists && c->empty_state) ||
            (c->exists && oc_equal(c->rec[1],"purge")));
        if ((kind==OP_INSTALL || kind==OP_UNINSTALL || (kind==OP_RECOVER && !cleanup_recover)) &&
            !oc_usb_fence(c))
            return api_err(c,"invalid_legacy_runtime");
    }

    if (kind==OP_ST_COMP || kind==OP_DM_DONE) return oc_handle_completion(c,kind==OP_DM_DONE);
    if (c->is_usb && kind==OP_ST_SET) return oc_handle_usb_meta(c);

    if (!c->is_usb && c->exists && !oc_equal(c->rec[1],"purge") && !oc_equal(c->rec[1],"removed")) {
        if (!c->sel_snap[0] || !oc_snap_package_only(c->data,c->sel_snap,c->settings_pkg) || oc_equal(c->settings_pkg,"-"))
            return api_err(c,"invalid_selected_snapshot");
    }
    if (kind==OP_ST_SET) return oc_api_emit_ctx(c,0,0);

    if (kind==OP_ST_FULL) {
        int conflict=0;
        if (c->exists && !oc_equal(c->rec[1],"purge")) {
            char id_before[384], id_after[384];
            if (!oc_status_identity(c->data,c->ram,id_before)) return api_err(c,"state_changed");
            if (oc_unlock(c->lock_fd)<0) return api_err(c,"invalid_lock");
            conflict=!oc_api_match_cur(c);
            if (oc_lock(c->lock_fd)<0) return api_err(c,"busy");
            if (!oc_check_session_pointer(c->ram,session_dir,c->ptr_name,c->owner,c->group)) return api_err(c,"session_replaced");
            if (!oc_status_identity(c->data,c->ram,id_after)) return api_err(c,"state_changed");
            if (!oc_equal(id_before,id_after)) return api_err(c,"busy");
        }
        return oc_api_emit_ctx(c,conflict,0);
    }

    if (c->is_usb) oc_usb_retain_clear(session_dir);

    int settled=c->exists && oc_rec_settled(c->rec);
    if (c->exists) {
        if (!oc_equal(rev,settled?c->rec[5]:c->rec[2])) return api_err(c,"stale_state");
        if (!settled) {
            if (kind!=OP_RECOVER) return api_err(c,"operation_pending");
            int removed_now=0;
            if (!oc_equal(c->rec[1],"purge")) {
                if (!oc_transaction_reconcile(c->root,c->root_path,c->data,c->rec,session_dir,0,c->owner,c->group,&c->err))
                    return OC_API_ERR;
                if (!oc_record_read_any(c->data,c->owner,c->group,c->rec_buf,sizeof c->rec_buf,c->rec))
                    return api_err(c,"invalid_record");
            }
            if (oc_equal(c->rec[1],"removed") || oc_equal(c->rec[1],"purge")) {
                if (!oc_uninstall_cleanup(c->root,c->root_path,c->data,session_dir,c->owner,c->group,&c->err))
                    return OC_API_ERR;
                (void)oc_close(c->data); c->data=-1; c->exists=0; c->empty_state=0; removed_now=1;
            }
            int conflict=c->exists && !oc_equal(c->rec[1],"purge") && !oc_api_match_cur(c);
            if (c->is_usb) oc_usb_retain_set(c->root,session_dir,c->exists,c->exists?c->rec[5]:"-");
            return oc_api_emit_ctx(c,conflict,removed_now);
        }
    } else if (!oc_equal(rev,"-")) return api_err(c,"stale_state");
    else if (c->empty_state && kind!=OP_RECOVER) return api_err(c,"operation_pending");

    if (kind==OP_RESTART) {
        if (c->exists) { if (!oc_api_match_cur(c)) return api_err(c,"state_changed"); }
        else if (!oc_data_absent(c->root)) return api_err(c,"operation_pending");
        if (!oc_mounts_mode(c->root,oc_mscratch,sizeof oc_mscratch,0)) return api_err(c,"root_mount_changed");
        if (c->is_usb) oc_usb_retain_set(c->root,session_dir,c->exists,c->exists?c->rec[5]:"-");
        if (!oc_spawn_reboot(c)) return api_err(c,"restart_failed");
        return oc_write_all(1,"{\"ok\":true,\"restarting\":true}\n",30) ? OC_API_DONE : OC_API_ERR;
    }
    if (kind==OP_RECOVER) {
        int removed_now=0;
        if (!c->exists && c->empty_state) {
            if (!oc_uninstall_cleanup(c->root,c->root_path,c->data,session_dir,c->owner,c->group,&c->err))
                return OC_API_ERR;
            (void)oc_close(c->data); c->data=-1; c->empty_state=0; removed_now=1;
        }
        int conflict=c->exists && !oc_equal(c->rec[1],"purge") && !oc_api_match_cur(c);
        if (c->is_usb) oc_usb_retain_set(c->root,session_dir,c->exists,c->exists?c->rec[5]:"-");
        return oc_api_emit_ctx(c,conflict,removed_now);
    }
    if (!oc_mounts_mode(c->root,oc_mscratch,sizeof oc_mscratch,0)) return api_err(c,"root_mount_changed");
    if (kind==OP_INSTALL) return oc_handle_install(c);
    if (kind==OP_UNINSTALL) return oc_handle_uninstall(c);
    if (kind==OP_IMPORT || kind==OP_ACC_SET) return oc_handle_access(c,kind==OP_IMPORT);
    if (kind==OP_EXPORT_PREFS) return oc_handle_export_prefs(c);
    if (kind==OP_IMPORT_PREFS) return oc_handle_import_prefs(c);
    return oc_handle_fast_set(c);
}

static int oc_api_handle_dir(const char *session_dir, const char *rev, const char *op,
                             const char *arg, const char *exp, const char *des) {
    int arg_dash = oc_equal(arg,"-"), kind = 0;
    if (oc_equal(op,"status")) {
        if (oc_equal(arg,"settings")) kind=OP_ST_SET;
        else if (oc_equal(arg,"completion")) kind=OP_ST_COMP;
        else if (arg_dash) kind=OP_ST_FULL;
    } else if (oc_equal(op,"dismiss")) {
        if (oc_equal(arg,"usb")) kind=OP_DM_USB;
        else if (arg_dash) kind=OP_DM_DONE;
    } else if (oc_equal(op,"set")) {
        kind=(oc_equal(arg,"uart")||oc_equal(arg,"ssh")) ? OP_ACC_SET : OP_FAST_SET;
    } else if (oc_equal(op,"export") && oc_equal(arg,"prefs")) {
        kind=OP_EXPORT_PREFS;
    } else if (oc_equal(op,"import") && oc_equal(arg,"prefs")) {
        kind=OP_IMPORT_PREFS;
    } else if (arg_dash) {
        if (oc_equal(op,"restart")) kind=OP_RESTART;
        else if (oc_equal(op,"install")) kind=OP_INSTALL;
        else if (oc_equal(op,"uninstall")) kind=OP_UNINSTALL;
        else if (oc_equal(op,"recover")) kind=OP_RECOVER;
        else if (oc_equal(op,"import")) kind=OP_IMPORT;
    }
    if (!kind) return emit_fail("invalid_request");

    static OcApiCtx ctx;
    OcApiCtx *c=&ctx;
    c->session_dir=session_dir; c->root_path=oc_root_path(); c->ptr_name="runtime";
    c->rev=rev; c->op=op; c->arg=arg; c->exp=exp; c->des=des;
    c->root=-1; c->ram=-1; c->lock_fd=-1; c->data=-1; c->snaps_fd=-1;
    c->is_usb=0; c->exists=0; c->empty_state=0;
    c->owner=oc_owner(); c->group=oc_group();
    c->sel_snap[0]=0; c->settings_pkg[0]=0; c->err=0;
    oc_diag_clear();

    int res=oc_api_dispatch(c,kind);
    if (c->snaps_fd>=0) (void)oc_close(c->snaps_fd);
    if (c->data>=0) (void)oc_close(c->data);
    if (c->lock_fd>=0) (void)oc_close(c->lock_fd);
    if (c->ram>=0) (void)oc_close(c->ram);
    if (c->root>=0) (void)oc_close(c->root);
    if (c->is_usb && c->err &&
        (kind==OP_INSTALL || kind==OP_UNINSTALL || kind==OP_RECOVER) &&
        !oc_equal(c->err,"busy") && !oc_equal(c->err,"operation_pending") &&
        !oc_equal(c->err,"session_closed") && !oc_equal(c->err,"session_replaced")) {
        oc_api_log_usb_failure(session_dir,op,c->err);
    }
    return c->err ? emit_fail(c->err) : res;
}

int oc_api_handle(const char *token_path, const char *rev, const char *op,
                  const char *arg, const char *exp, const char *des) {
    char session_dir[512];
    unsigned tlen=oc_length(token_path);
    if (tlen<7 || !oc_equal(token_path+tlen-6,"/token") || tlen-6>=sizeof session_dir) return OC_API_FALLBACK;
    for (unsigned i=0; i<tlen-6; ++i) session_dir[i]=token_path[i];
    session_dir[tlen-6]=0;
    return oc_api_handle_dir(session_dir,rev,op,arg,exp,des);
}

/* ---------- Internal CLI subcommands (host tests) ---------- */
int oc_api_cli(int argc, char **argv) {
#ifdef OC_HOST
    if (oc_equal(argv[1],"--handle") && argc==8) {
        int r=oc_api_handle_dir(argv[2],argv[3],argv[4],argv[5],argv[6],argv[7]);
        return r==OC_API_DONE ? 0 : 1;
    }
    const char *root_path=oc_root_path();
    long owner=oc_owner(), group=oc_group();
    int root=(int)oc_openat(OC_CWD,root_path,OC_DIRECTORY,0);
    if (root<0) return 1;
    int rc=64;

    if (oc_equal(argv[1],"--nvram") && argc>=3) {
        if (oc_equal(argv[2],"read") && argc==3) {
            char nv[16];
            if (oc_nvram_at(root,nv) && oc_write_all(1,nv,oc_length(nv)) && oc_write_all(1,"\n",1)) rc=0;
            else rc=1;
        } else if (oc_equal(argv[2],"change") && argc==5) {
            rc=oc_nvram_change(root,argv[3],argv[4]) ? 0 : 1;
        }
    } else if (oc_equal(argv[1],"--test-root-publish") && argc==13) {
        int data=oc_open_data_dir(root);
        if (data>=0) {
            int ok=oc_root_publish(root,root_path,data,argv[2],argv[3],argv[4],argv[5],argv[6],argv[7],
                                   oc_equal(argv[8],"-")?0:argv[8],oc_equal(argv[9],"-")?0:argv[9],
                                   oc_equal(argv[10],"1"),oc_equal(argv[11],"-")?0:argv[11]);
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
    }
    (void)oc_close(root);
    return rc;
#else
    (void)argc; (void)argv;
    return 64;
#endif
}
