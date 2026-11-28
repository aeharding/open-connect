/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Shared profile renderers (index.html, sm-*.conf, mmui.xml, vui-plugins.list)
 * linked into both api and install so maintenance and install share one path.
 */
#include "oc-core.h"

#ifdef OC_HOST
#include <stdlib.h>
#endif

static struct {
    char mf_buf[8192];
    char hook_buf[8192];
    char log_buf[1024];
    char line_buf[4096];
    char out_buf[8192];
} oc_rmem;

static char *oc_rfind(char *s, const char *sub) {
    for (; *s; ++s) if (oc_prefix(s,sub)) return s;
    return 0;
}

static int oc_rwrite_str(int fd, const char *s) { return oc_write_all(fd,s,oc_length(s)); }

typedef struct { int fd; char buf[4096]; unsigned at, filled, total, limit; OcHash *hash; } OcRStream;

static int oc_rstream_line(OcRStream *s, char *out, unsigned cap, int *had_nl) {
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

int oc_verify_file_sha(int dir, const char *name, const char *expected, oc_u64 limit) {
    char dig[65]; OcMeta fm;
    return expected && oc_hash_file_at(dir,name,dig,&fm) && fm.size<=limit && oc_equal(dig,expected);
}

int oc_open_pkg_verified(int data, const char *pkg_id, char *mf_buf, unsigned mf_cap, OcManifest *mf) {
    int pdir=oc_open_sub(data,"packages",pkg_id);
    if (pdir<0) return -1;
    if (!oc_verified_text(pdir,"files.sha256",pkg_id,mf_buf,mf_cap) ||
        !oc_manifest(mf_buf,mf,0)) { (void)oc_close(pdir); return -1; }
    return pdir;
}

int oc_open_composed_verified(int data_fd, const char *pkg_id, const char *snap_id,
                              char cmf_buf[4096], OcManifest *cmf) {
    int cdir=oc_open_sub(data_fd,"composed",pkg_id);
    if (cdir<0) return -1;
    if (snap_id) {
        char dep_key[96]; OcManifest dmf, smf;
        int cs_fd=oc_open_sub(data_fd,"snapshots",snap_id);
        int cok=cs_fd>=0 &&
            oc_verified_text(cs_fd,"files.sha256",snap_id,oc_mscratch,sizeof oc_mscratch) && oc_manifest(oc_mscratch,&smf,0) &&
            oc_saved_text(cs_fd,&smf,"dependencies",oc_big_buf,sizeof oc_big_buf) && oc_manifest(oc_big_buf,&dmf,1) &&
            oc_join4(dep_key,sizeof dep_key,"composed-",pkg_id,"/files.sha256",0);
        const char *cdig=cok?oc_digest(&dmf,dep_key):0;
        if (cs_fd>=0) (void)oc_close(cs_fd);
        if (!cok || !cdig || !oc_verified_text(cdir,"files.sha256",cdig,cmf_buf,4096) || !oc_manifest(cmf_buf,cmf,0)) {
            (void)oc_close(cdir); return -1;
        }
        return cdir;
    }
    /* Fresh install path (no prior snapshot yet): load & hash composed/files.sha256 directly. */
    if (oc_text(cdir,"files.sha256",cmf_buf,4096,0)<=0 || !oc_manifest(cmf_buf,cmf,0) ||
        cmf->count!=12 || !oc_members(cdir,cmf,1)) {
        (void)oc_close(cdir); return -1;
    }
    return cdir;
}

int oc_run_awk_profile(const char *dbase, const char *pkg_id, const char *cfg_path,
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
    int rc=oc_run_cmd(awk_bin,argv,(int)ofd,0,0,-1);
    int ok=(rc==0) && oc_mode((int)ofd,0600)>=0 && oc_sync((int)ofd)>=0;
    if (oc_close((int)ofd)<0) ok=0;
    return ok;
}

int oc_render_index_native(int pkg_fd, OcManifest *pkg_mf,
                           int comp_fd, OcManifest *comp_mf,
                           int work_fd, const OcPrefs *p) {
    const char *tpl_name=oc_equal(p->warning,"1")?"index-on.html":"index-off.html";
    const char *tpl_dig=oc_digest(comp_mf,tpl_name);
    if (!tpl_dig) return 0;

    int is_base=oc_equal(p->base,"1"), is_warn=oc_equal(p->warning,"1"),
        is_as=oc_equal(p->autoshow,"1"), is_so=oc_equal(p->source_order,"1");
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
    int nd=is_warn || hlen>0 || is_so;

    if (nd && !oc_verified_text(pkg_fd,"system-hook.js",oc_digest(pkg_mf,"system-hook.js"),oc_rmem.hook_buf,sizeof oc_rmem.hook_buf)) return 0;
    if (is_base && !oc_verified_text(pkg_fd,"base-logging.js",oc_digest(pkg_mf,"base-logging.js"),oc_rmem.log_buf,sizeof oc_rmem.log_buf)) return 0;

    long tfd=oc_openat(comp_fd,tpl_name,OC_READ,0);
    if (tfd<0) return 0;
    OcMeta tm;
    if (oc_stat((int)tfd,&tm)<0 || (tm.mode&OC_TYPE)!=OC_REGULAR) { (void)oc_close((int)tfd); return 0; }
    long ofd=oc_openat(work_fd,"index.html",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (ofd<0) { (void)oc_close((int)tfd); return 0; }

    OcHash th; oc_hash_init(&th);
    OcRStream st; st.fd=(int)tfd; st.at=st.filled=st.total=0; st.limit=262144; st.hash=&th;
    unsigned lg=0, hk=0, ap=0, tok_cnt=0;
    int ok=1, had_nl=0, r;
    while (ok && (r=oc_rstream_line(&st,oc_rmem.line_buf,sizeof oc_rmem.line_buf,&had_nl))==1) {
        char *line=oc_rmem.line_buf;
        for (const char *s=line; *s; ++s) if (oc_prefix(s,"@TOKEN@")) ++tok_cnt;
        int is_log=is_base && oc_rfind(line,"src=\"common/js/logDefaults.js\"")!=0;
        if (is_log) {
            ok=oc_rwrite_str((int)ofd,line) && oc_rwrite_str((int)ofd,"\n<script>\n") &&
               oc_rwrite_str((int)ofd,oc_rmem.log_buf);
            unsigned lb=oc_length(oc_rmem.log_buf);
            if (ok && (!lb || oc_rmem.log_buf[lb-1]!='\n')) ok=oc_rwrite_str((int)ofd,"\n");
            if (ok) ok=oc_rwrite_str((int)ofd,"</script>\n");
            ++lg; continue;
        }
        if (oc_rfind(line,"framework.init();")) {
            if (nd) {
                int ab=0, sb=0;
                char *hp=oc_rmem.hook_buf;
                while (ok && *hp) {
                    char *hl=hp;
                    while (*hp && *hp!='\n') ++hp;
                    if (*hp=='\n') *hp++=0;
                    if (oc_rfind(hl,"/* OPEN_CONNECT_AA_BEGIN */")) { ab=1; continue; }
                    if (oc_rfind(hl,"/* OPEN_CONNECT_AA_END */")) { ab=0; continue; }
                    if (oc_rfind(hl,"/* OPEN_CONNECT_SO_BEGIN */")) { sb=1; continue; }
                    if (oc_rfind(hl,"/* OPEN_CONNECT_SO_END */")) { sb=0; continue; }
                    char *call_pos=oc_rfind(hl," /* OPEN_CONNECT_AA_CALL */");
                    int has_call=call_pos!=0 || oc_rfind(hl,"/* OPEN_CONNECT_AA_CALL */")!=0;
                    if (!ag && (ab || has_call)) continue;
                    char *so_pos=oc_rfind(hl," /* OPEN_CONNECT_SO_CALL */");
                    int has_so=so_pos!=0 || oc_rfind(hl,"/* OPEN_CONNECT_SO_CALL */")!=0;
                    if (!is_so && (sb || has_so)) continue;
                    char *ap_pos=oc_rfind(hl,"/*OPEN_CONNECT_APPLIED*/");
                    while (*hl==' '||*hl=='\t') ++hl;
                    unsigned at=0;
                    for (char *s=hl; ok && *s; ) {
                        if (call_pos && s==call_pos) { s+=27; call_pos=0; continue; }
                        if (so_pos && s==so_pos) { s+=27; so_pos=0; continue; }
                        if (ap_pos && s==ap_pos) {
                            const char *parts[5]={p->warning,",\"",h,"\"",is_so?",1":""};
                            for (unsigned k=0; k<5; ++k) {
                                unsigned pl=oc_length(parts[k]);
                                if (at+pl+2>=sizeof oc_rmem.out_buf) { ok=0; break; }
                                for (unsigned j=0; j<pl; ++j) oc_rmem.out_buf[at++]=parts[k][j];
                            }
                            s+=24; ap_pos=0; ++ap; continue;
                        }
                        if (at+2>=sizeof oc_rmem.out_buf) { ok=0; break; }
                        oc_rmem.out_buf[at++]=*s++;
                    }
                    if (ok) {
                        oc_rmem.out_buf[at++]='\n';
                        ok=oc_write_all((int)ofd,oc_rmem.out_buf,at);
                    }
                }
                ++hk;
            }
            if (ok && is_as)
                ok=oc_rwrite_str((int)ofd,"</script>\n<script src=\"file:///tmp/open-connect/feature/carplay.js\"></script>\n<script>\n");
        }
        if (ok) ok=oc_rwrite_str((int)ofd,line) && (!had_nl || oc_write_all((int)ofd,"\n",1));
    }
    char got_dig[65]; oc_hash_finish(&th,got_dig);
    if (r<0 || (oc_u64)st.total!=tm.size || !oc_equal(got_dig,tpl_dig)) ok=0;
    if (ok) ok=oc_mode((int)ofd,0600)>=0 && oc_sync((int)ofd)>=0;
    if (oc_close((int)ofd)<0) ok=0;
    (void)oc_close((int)tfd);
    return ok && (!is_base || lg==1) && (!nd || (hk==1 && ap==1)) && tok_cnt==1;
}

static int oc_verify_pkg_awk_inputs(int pdir, OcManifest *pmf, const char *const *names,
                                    unsigned count, oc_u64 *cat_sz) {
    for (unsigned i=0; i<count; ++i)
        if (!oc_verify_file_sha(pdir,names[i],oc_digest(pmf,names[i]),262144)) return 0;
    OcMeta cm={0};
    long cfd=oc_openat(pdir,"services.tsv",OC_READ,0);
    int ok=cfd>=0 && oc_stat((int)cfd,&cm)>=0;
    if (cfd>=0) (void)oc_close((int)cfd);
    if (ok) *cat_sz=cm.size;
    return ok;
}

int oc_render_sm_profiles(int data_fd, const char *root_path, const char *pkg_id,
                          const char *snap_id, const char *cfg_path, unsigned cfg_len,
                          const char *warning_val, int out_dir) {
    OcManifest pmf, cmf; char cmf_buf[4096], dbase[320], cfg_len_s[24], cat_len_s[24];
    int pdir=oc_open_pkg_verified(data_fd,pkg_id,oc_rmem.out_buf,sizeof oc_rmem.out_buf,&pmf);
    if (pdir<0) return 0;
    const char *nf[3]={"preferences.awk","services.tsv","sm-profile.awk"};
    oc_u64 cat_sz=0;
    int ok=oc_verify_pkg_awk_inputs(pdir,&pmf,nf,3,&cat_sz);
    (void)oc_close(pdir);
    int cdir=ok?oc_open_composed_verified(data_fd,pkg_id,snap_id,cmf_buf,&cmf):-1;
    if (cdir<0) return 0;
    oc_u64_dec((oc_u64)cfg_len,cfg_len_s); oc_u64_dec(cat_sz,cat_len_s);
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

int oc_render_ui_profiles(int data_fd, const char *root_path, const char *pkg_id,
                          const char *cfg_path, unsigned cfg_len,
                          int need_mmui, int need_plugins, int out_dir) {
    if (!need_mmui && !need_plugins) return 1;
    OcManifest pmf; char dbase[320], cfg_len_s[24], cat_len_s[24];
    int pdir=oc_open_pkg_verified(data_fd,pkg_id,oc_rmem.out_buf,sizeof oc_rmem.out_buf,&pmf);
    if (pdir<0) return 0;
    const char *nf[4]={"preferences.awk","services.tsv","ui-profile.awk","ui-modules.tsv"};
    oc_u64 cat_sz=0;
    int ok=oc_verify_pkg_awk_inputs(pdir,&pmf,nf,4,&cat_sz) && oc_data_base(root_path,dbase,sizeof dbase);
    (void)oc_close(pdir);
    if (!ok) return 0;
    oc_u64_dec((oc_u64)cfg_len,cfg_len_s); oc_u64_dec(cat_sz,cat_len_s);
    if (need_mmui) {
        int orig=oc_open_private(data_fd,"originals");
        int mok=orig>=0 && oc_verify_file_sha(orig,"mmui.xml",
            oc_pin_digest("originals/mmui.xml","ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0"),262144);
        if (orig>=0) (void)oc_close(orig);
        char mmui_in[320];
        ok=mok && oc_join(mmui_in,sizeof mmui_in,dbase,"/originals/mmui.xml") &&
            oc_run_awk_profile(dbase,pkg_id,cfg_path,cfg_len_s,cat_len_s,"ui-profile.awk","mmui",mmui_in,out_dir,"mmui.xml");
    }
    if (ok && need_plugins)
        ok=oc_run_awk_profile(dbase,pkg_id,cfg_path,cfg_len_s,cat_len_s,"ui-profile.awk","plugins","/dev/null",out_dir,"vui-plugins.list");
    return ok;
}

int oc_render_all_profiles(int data_fd, const char *root_path, const char *pkg_id,
                           const char *cfg_path, unsigned cfg_len,
                           const OcPrefs *p, int out_dir) {
    OcManifest pmf, cmf; char cmf_buf[4096];
    int pdir=oc_open_pkg_verified(data_fd,pkg_id,oc_rmem.mf_buf,sizeof oc_rmem.mf_buf,&pmf);
    int cdir=pdir>=0 ? oc_open_composed_verified(data_fd,pkg_id,0,cmf_buf,&cmf) : -1;
    int ok=pdir>=0 && cdir>=0 && oc_render_index_native(pdir,&pmf,cdir,&cmf,out_dir,p);
    if (cdir>=0) (void)oc_close(cdir);
    if (pdir>=0) (void)oc_close(pdir);
    if (ok) ok=oc_render_ui_profiles(data_fd,root_path,pkg_id,cfg_path,cfg_len,1,1,out_dir);
    if (ok) ok=oc_render_sm_profiles(data_fd,root_path,pkg_id,0,cfg_path,cfg_len,p->warning,out_dir);
    return ok;
}
