/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native maintenance transaction engine: snapshot loading, target/dependency
 * verification, snapshot creation & boot.plan sealing, durable prepare/reconcile,
 * and RAM-resident uninstall purge.
 */
#include "oc-core.h"

OcTxnSnap oc_snap_pool[7];
char oc_mscratch[8192];
char oc_big_buf[32768];

static int oc_txn_parse_cfg(char *text, OcTxnSnap *s) {
    OcPrefs p;
    int active=oc_prefix(text,"OC2\n");
    if (!oc_prefs_parse(text,0,active,&p)) return 0;
    s->is_oc2=p.is_oc2;
    return oc_join(s->pkg,65,"",p.package) && oc_join(s->touch,4,"",p.touch) &&
        oc_join(s->warning,4,"",p.warning) && oc_join(s->base,4,"",p.base) &&
        oc_join(s->nvram,16,"",p.nvram) && oc_join(s->meta,40,"",p.metadata);
}

int oc_txn_read_snap(int data_fd, const char *snap_id, OcTxnSnap *s) {
    oc_u8 *zb=(oc_u8 *)s;
    for (unsigned i=0; i<sizeof *s; ++i) zb[i]=0;
    (void)oc_join(s->sel_hash,65,"","-"); (void)oc_join(s->sel_meta,40,"","-");
    (void)oc_join(s->sel_pkg,65,"","-");
    char path[128];
    if (!oc_hex(snap_id,64) || !oc_join(path,sizeof path,"snapshots/",snap_id)) return 0;
    int sdir=oc_open_private(data_fd,path);
    if (sdir<0) return 0;
    OcMeta m={0};
    const char *ad=0;
    int ok=oc_load_manifest(sdir,snap_id,s->mf_buf,sizeof s->mf_buf,&s->mf) &&
        oc_saved_text(sdir,&s->mf,"config",s->cfg_buf,sizeof s->cfg_buf) &&
        oc_txn_parse_cfg(s->cfg_buf,s) &&
        (ad=oc_digest(&s->mf,"autostart"))!=0 &&
        oc_hash_file_at(sdir,"autostart",s->auto_dig,&m) && oc_equal(s->auto_dig,ad);
    if (ok) {
        if (oc_digest(&s->mf,"access")) {
            const char *ld=oc_digest(&s->mf,"runlogin"), *sd=oc_digest(&s->mf,"sshd.conf");
            ok=ld && sd &&
                oc_saved_text(sdir,&s->mf,"access",s->acc_buf,sizeof s->acc_buf) &&
                oc_access(s->acc_buf,s->acc_f) &&
                oc_hash_file_at(sdir,"runlogin",s->login_dig,&m) && oc_equal(s->login_dig,ld) &&
                oc_hash_file_at(sdir,"sshd.conf",s->ssh_dig,&m) && oc_equal(s->ssh_dig,sd);
            if (ok) s->has_access=1;
        } else if (!oc_absent_at(sdir,"access")) {
            ok=0;
        }
    }
    if (ok) {
        if (oc_digest(&s->mf,"selector")) {
            s->has_selector=1;
            ok=oc_saved_text(sdir,&s->mf,"selector",s->sel_buf,sizeof s->sel_buf);
            if (ok && !oc_equal(s->sel_buf,"-\n")) {
                char *f[3]; unsigned pm, pu, pg;
                ok=oc_fields_line(s->sel_buf,f,3) && oc_hex(f[0],64) && oc_hex(f[2],64) &&
                    oc_metadata_mode(f[1],&pm,&pu,&pg) &&
                    !oc_equal(s->pkg,"-") && oc_equal(f[2],s->pkg) &&
                    pm==0700 && pu==(unsigned)oc_owner() && pg==(unsigned)oc_group() &&
                    oc_join(s->sel_hash,65,"",f[0]) && oc_join(s->sel_meta,40,"",f[1]) &&
                    oc_join(s->sel_pkg,65,"",f[2]);
            }
        } else if (!oc_absent_at(sdir,"selector")) {
            ok=0;
        }
    }
    for (unsigned i=0; ok && i<s->mf.count; ++i) {
        const char *nm=s->mf.rows[i].name;
        if (oc_equal(nm,"config") || oc_equal(nm,"autostart") ||
            (s->has_access && (oc_equal(nm,"access") || oc_equal(nm,"runlogin") || oc_equal(nm,"sshd.conf"))) ||
            (s->has_selector && oc_equal(nm,"selector"))) continue;
        char dig[65];
        ok=oc_hash_file_at(sdir,nm,dig,&m) && oc_equal(dig,s->mf.rows[i].digest);
    }
    if (oc_close(sdir)<0) ok=0;
    return ok;
}

int oc_targets_match(int root, int data_fd, const char *snap_id, const char *base_snap,
                     long owner, long group) {
    OcTxnSnap *s=&oc_snap_pool[2];
    if (!oc_txn_read_snap(data_fd,snap_id,s)) return 0;
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    char adig[65], ams[40], nv[16]; OcMeta am={0};
    int ok=ubin>=0 && oc_hash_file_at((int)ubin,"autostart",adig,&am) &&
        oc_equal(adig,s->auto_dig) && oc_meta_mode_str(&am,ams) && oc_equal(ams,s->meta) &&
        oc_nvram_at(root,nv) && oc_equal(nv,s->nvram);
    if (ubin>=0 && oc_close((int)ubin)<0) ok=0;
    if (ok && s->has_access) ok=oc_access_targets_match(root,data_fd,snap_id,base_snap,owner,group);
    if (ok && s->has_selector) ok=oc_selector_matches_at(root,s->sel_hash,s->sel_meta);
    return ok;
}

static const char *oc_root_path_lookup(const char *leaf) {
    for (unsigned i=0; i<19; ++i) if (oc_equal(leaf,oc_root_names[i])) return oc_root_paths[i];
    return 0;
}

static int oc_dep_line_parse(char *ln, const char **dig_out, const char **key_out,
                             char scope[96], const char **leaf_out) {
    if (oc_length(ln)<67 || ln[64]!=' ' || ln[65]!=' ') return 0;
    ln[64]=0;
    const char *dig=ln, *key=ln+66, *sl=0;
    if (!oc_hex(dig,64)) return 0;
    for (const char *q=key; *q; ++q) { if (*q=='/') { if (sl) return 0; sl=q; } }
    if (!sl || sl==key || !sl[1] || !oc_key(sl+1)) return 0;
    unsigned slen=(unsigned)(sl-key);
    if (slen>=96) return 0;
    for (unsigned i=0; i<slen; ++i) scope[i]=key[i];
    scope[slen]=0;
    *dig_out=dig; *key_out=key; *leaf_out=sl+1;
    return 1;
}

static char oc_dep_buf[24576];

int oc_dependencies_match(int root, int data_fd, const char *snap_id, long owner, long group) {
    (void)owner; (void)group;
    char path[128], mf_buf[4096]; OcManifest mf;
    if (!oc_hex(snap_id,64) || !oc_join(path,sizeof path,"snapshots/",snap_id)) return 0;
    int sdir=oc_open_private(data_fd,path);
    if (sdir<0) return 0;
    int ok=oc_load_manifest(sdir,snap_id,mf_buf,sizeof mf_buf,&mf) &&
        oc_saved_text(sdir,&mf,"dependencies",oc_dep_buf,sizeof oc_dep_buf);
    if (oc_close(sdir)<0) ok=0;
    if (!ok) return 0;
    if (!oc_dep_buf[0]) return 1;

    char *p=oc_dep_buf;
    int cached_fd=-1; char cached_scope[96]; cached_scope[0]=0;
    while (ok && *p) {
        char *ln=p;
        while (*p && *p!='\n') ++p;
        if (!*p) { ok=0; break; }
        *p++=0;
        const char *dig, *key, *leaf; char scope[96];
        if (!oc_dep_line_parse(ln,&dig,&key,scope,&leaf)) { ok=0; break; }
        char got[65]; OcMeta m={0};
        if (oc_equal(scope,"root")) {
            const char *rpath=oc_root_path_lookup(leaf);
            if (!rpath) { ok=0; break; }
            long fd=oc_beneath(root,rpath+1,OC_READ,0);
            ok=fd>=0 && oc_hash_copy((int)fd,-1,33554432,got,&m)==OC_COPY_OK && oc_equal(got,dig);
            if (fd>=0 && oc_close((int)fd)<0) ok=0;
        } else if (oc_prefix(scope,"package-") || oc_prefix(scope,"composed-")) {
            int is_comp=oc_prefix(scope,"composed-");
            const char *id=scope+(is_comp?9:8);
            if (!oc_hex(id,64)) { ok=0; break; }
            if (!oc_equal(scope,cached_scope)) {
                if (cached_fd>=0) (void)oc_close(cached_fd);
                char rel[96];
                cached_fd=(oc_join(rel,sizeof rel,is_comp?"composed/":"packages/",id))
                    ? oc_open_private(data_fd,rel) : -1;
                if (cached_fd<0 || !oc_join(cached_scope,sizeof cached_scope,"",scope)) { ok=0; break; }
            }
            ok=oc_hash_file_at(cached_fd,leaf,got,&m) && oc_equal(got,dig);
        } else {
            ok=0; break;
        }
    }
    if (cached_fd>=0 && oc_close(cached_fd)<0) ok=0;
    return ok;
}

static int oc_deps_equal(int data_fd, const char *a_id, const char *b_id) {
    if (oc_equal(a_id,b_id)) return 1;
    OcTxnSnap *sa=&oc_snap_pool[2], *sb=&oc_snap_pool[3];
    if (!oc_txn_read_snap(data_fd,a_id,sa) || !oc_txn_read_snap(data_fd,b_id,sb)) return 0;
    const char *da=oc_digest(&sa->mf,"dependencies"), *db=oc_digest(&sb->mf,"dependencies");
    return da && db && oc_equal(da,db);
}

int oc_dependencies_pair_match(int root, int data_fd, const char *before_id, const char *after_id,
                               long owner, long group) {
    if (!oc_dependencies_match(root,data_fd,before_id,owner,group)) return 0;
    if (oc_deps_equal(data_fd,before_id,after_id)) {
        return oc_txn_read_snap(data_fd,after_id,&oc_snap_pool[2]);
    }
    return oc_dependencies_match(root,data_fd,after_id,owner,group);
}

int oc_uninstall_owned(int data_fd, const char *snap_id, const char *base_snap, long owner, long group) {
    (void)owner; (void)group;
    OcTxnSnap *cur=&oc_snap_pool[2], *base=&oc_snap_pool[3];
    if (!oc_txn_read_snap(data_fd,snap_id,cur) || !oc_txn_read_snap(data_fd,base_snap,base)) return 0;
    if (!oc_hex(cur->pkg,64)) return 0;
    char cpath[128], cdig[65]; OcMeta cm={0};
    if (!oc_join4(cpath,sizeof cpath,"composed/",cur->pkg,"/autostart",0)) return 0;
    long fd=oc_beneath(data_fd,cpath,OC_READ,0);
    int ok=fd>=0 && oc_hash_copy((int)fd,-1,33554432,cdig,&cm)==OC_COPY_OK && oc_equal(cdig,cur->auto_dig);
    if (fd>=0 && oc_close((int)fd)<0) ok=0;
    if (!ok || !oc_equal(cur->meta,base->meta)) return 0;
    return oc_equal(cur->nvram,base->nvram) || (oc_equal(cur->touch,"1") && oc_equal(cur->nvram,"disable"));
}

static int oc_txn_copy_sync(int src_dir, const char *src_name, int dst_dir, const char *dst_name, char digest[65]) {
    return oc_copy_file_at(src_dir,src_name,dst_dir,dst_name,0600,1,1,digest);
}

typedef struct { char names[32][128]; unsigned count; int more, ok; const char *skip; } OcRmBatch;
static int oc_rm_collect_cb(const char *name, void *raw) {
    OcRmBatch *b=raw;
    if (b->skip && oc_equal(name,b->skip)) return 1;
    if (b->count==32) { b->more=1; return 0; }
    if (!oc_join(b->names[b->count],128,"",name)) { b->ok=0; return 0; }
    ++b->count;
    return 1;
}
static int oc_rm_tree_cb_cleanup(int dir_fd, oc_u64 dev, const char *skip, unsigned depth) {
    if (depth>8) return 0;
    for (unsigned pass=0; pass<64; ++pass) {
        OcRmBatch b; b.count=0; b.more=0; b.ok=1; b.skip=skip;
        if (!oc_dir_iter(dir_fd,oc_rm_collect_cb,&b) || !b.ok) return 0;
        if (!b.count) return 1;
        for (unsigned i=0; i<b.count; ++i) {
            OcMeta m={0};
            if (oc_metadata(dir_fd,b.names[i],&m)<0 || m.device!=dev) return 0;
            if ((m.mode&OC_TYPE)==OC_DIR) {
                long sub=oc_openat(dir_fd,b.names[i],OC_DIRECTORY,0);
                if (sub<0) return 0;
                int rok=oc_rm_tree_cb_cleanup((int)sub,dev,0,depth+1);
                if (oc_close((int)sub)<0 || !rok || oc_rmdirat(dir_fd,b.names[i])<0) return 0;
            } else if (oc_unlink(dir_fd,b.names[i])<0) return 0;
        }
        if (!b.more) return 1;
    }
    return 0;
}

void oc_rm_subdir(int parent, const char *leaf) {
    OcMeta pm={0};
    if (oc_stat(parent,&pm)<0) return;
    long sub=oc_openat(parent,leaf,OC_DIRECTORY,0);
    if (sub>=0) {
        (void)oc_rm_tree_cb_cleanup((int)sub,pm.device,0,0);
        (void)oc_close((int)sub);
        (void)oc_rmdirat(parent,leaf);
    }
}

int oc_mounts_has(int root, const char *target, const char *fstype, int prefix_match) {
    if (oc_text(root,"proc/self/mounts",oc_mscratch,sizeof oc_mscratch,1)<0) return -1;
    char pref[324];
    if (prefix_match && !oc_join(pref,sizeof pref,target,"/")) return -1;
    int hits=0; char *p=oc_mscratch;
    while (*p) {
        char *f[6]; unsigned n=0;
        while (*p && *p!='\n') {
            if (*p==' '||*p=='\t') { ++p; continue; }
            if (n==6) return -1;
            f[n++]=p;
            while (*p && *p!=' ' && *p!='\t' && *p!='\n') ++p;
            if (*p==' '||*p=='\t') *p++=0;
        }
        if (!*p || n!=6) return -1;
        *p++=0;
        int match = oc_equal(f[1],target) || (prefix_match && oc_prefix(f[1],pref));
        if (match && (!fstype || oc_equal(f[2],fstype))) ++hits;
    }
    return hits;
}

int oc_pkg_boot_select(int data_fd, const char *root_path, const char *pkg_id,
                       long owner, long group, char bs_path[512]) {
    if (!oc_hex(pkg_id,64)) return -1;
    char ppath[128], dbase[320]; OcManifest pmf;
    if (!oc_join(ppath,sizeof ppath,"packages/",pkg_id)) return -1;
    int pdir=oc_open_private(data_fd,ppath);
    if (pdir<0) return -1;
    int pok=oc_load_manifest(pdir,pkg_id,oc_mscratch,sizeof oc_mscratch,&pmf);
    const char *bd=pok?oc_digest(&pmf,"boot-select"):0;
    if (pok && !bd) {
        int abs=oc_absent_at(pdir,"boot-select");
        (void)oc_close(pdir);
        return abs?0:-1;
    }
    char bdig[65]; OcMeta bm={0};
    pok=pok && oc_hash_file_at(pdir,"boot-select",bdig,&bm) &&
        bm.mode==(OC_REGULAR|0700) && bm.uid==(unsigned)owner && bm.gid==(unsigned)group &&
        oc_equal(bdig,bd) && oc_data_base(root_path,dbase,sizeof dbase) &&
        oc_join4(bs_path,512,dbase,"/packages/",pkg_id,"/boot-select");
    (void)oc_close(pdir);
    return pok?1:-1;
}

static int oc_finish_snapshot_dir(int data_fd, int snaps, int wfd, const char *wleaf,
                                  const char *mnames[], char mdigs[][65], unsigned mc, char out_id[65]) {
    char snap_id[65]; snap_id[0]=0;
    long mfd=oc_openat(wfd,"files.sha256",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    OcHash h; oc_hash_init(&h);
    int ok=mfd>=0;
    for (unsigned i=0; ok && i<mc; ++i) {
        char row[160];
        ok=oc_join4(row,sizeof row,mdigs[i],"  ",mnames[i],"\n");
        if (ok) {
            unsigned rl=oc_length(row);
            oc_hash_add(&h,row,rl);
            ok=oc_write_all((int)mfd,row,rl);
        }
    }
    if (ok) {
        oc_hash_finish(&h,snap_id);
        ok=oc_mode((int)mfd,0600)>=0 && oc_sync((int)mfd)>=0;
    }
    if (mfd>=0 && oc_close((int)mfd)<0) ok=0;
    if (ok) ok=oc_sync(wfd)>=0;
    if (oc_close(wfd)<0) ok=0;
    if (ok) {
        if (oc_absent_at(snaps,snap_id)) {
            ok=oc_rename(snaps,wleaf,snap_id)>=0 && oc_sync(snaps)>=0;
        } else {
            oc_rm_subdir(snaps,wleaf);
            ok=oc_txn_read_snap(data_fd,snap_id,&oc_snap_pool[2]) && oc_sync(snaps)>=0;
        }
    }
    if (!ok) oc_rm_subdir(snaps,wleaf);
    return ok && oc_join(out_id,65,"",snap_id);
}

int oc_snapshot_create(int root, int data_fd, const char *autostart_snap, const char *pkg_id,
                       const char *nvram, const char *mode_str, const char *deps_snap,
                       int res_dir, const char *prefs_text, const char *session_dir,
                       const char *root_path, long owner, long group, char out_id[65]) {
    (void)session_dir; (void)root_path; (void)owner; (void)group;
    int snaps=oc_open_private(data_fd,"snapshots");
    if (snaps<0) return 0;
    char nonce[33], wleaf[48];
    if (!oc_random(root,nonce) || !oc_join(wleaf,sizeof wleaf,".new-",nonce) ||
        oc_mkdir(snaps,wleaf,0700)<0) { (void)oc_close(snaps); return 0; }
    int wfd=oc_open_private(snaps,wleaf);
    if (wfd<0) { oc_rm_subdir(snaps,wleaf); (void)oc_close(snaps); return 0; }

    const char *mnames[13]; char mdigs[13][65]; unsigned mc=0;
    int ok=1;
    {
        int adir=oc_open_private(snaps,autostart_snap);
        ok=adir>=0 && oc_txn_copy_sync(adir,"autostart",wfd,"autostart",mdigs[mc]);
        if (adir>=0 && oc_close(adir)<0) ok=0;
        if (ok) mnames[mc++]="autostart";
    }
    if (ok) {
        char cfg[1024];
        if (prefs_text && *prefs_text) ok=oc_join(cfg,sizeof cfg,"",prefs_text);
        else ok=oc_join4(cfg,sizeof cfg,pkg_id,"|0|0|",nvram,0) &&
                oc_join4(cfg,sizeof cfg,cfg,"|",mode_str,"\n");
        if (ok) {
            OcMeta cm={0};
            ok=oc_new_text(wfd,"config",cfg,0600) &&
                oc_hash_file_at(wfd,"config",mdigs[mc],&cm);
            long cfd=ok?oc_openat(wfd,"config",OC_READ,0):-1;
            if (cfd>=0) { if (oc_sync((int)cfd)<0) ok=0; if (oc_close((int)cfd)<0) ok=0; }
            else ok=0;
            if (ok) mnames[mc++]="config";
        }
    }
    if (ok) {
        int ddir=oc_open_private(snaps,deps_snap);
        ok=ddir>=0 && oc_txn_copy_sync(ddir,"dependencies",wfd,"dependencies",mdigs[mc]);
        if (ddir>=0 && oc_close(ddir)<0) ok=0;
        if (ok) mnames[mc++]="dependencies";
    }
    if (ok && res_dir>=0) {
        const char *opt[9]={"access","runlogin","sshd.conf","selector",
            "sm-normal.conf","sm-wcp.conf","index.html","mmui.xml","vui-plugins.list"};
        unsigned lim=(!oc_equal(pkg_id,"-") && prefs_text && *prefs_text)?9:4;
        for (unsigned i=0; ok && i<lim; ++i) {
            if (oc_absent_at(res_dir,opt[i])) continue;
            if (mc>=12) { ok=0; break; }
            ok=oc_txn_copy_sync(res_dir,opt[i],wfd,opt[i],mdigs[mc]);
            if (ok) mnames[mc++]=opt[i];
        }
    }
    if (ok) ok=oc_finish_snapshot_dir(data_fd,snaps,wfd,wleaf,mnames,mdigs,mc,out_id);
    else { (void)oc_close(wfd); oc_rm_subdir(snaps,wleaf); }
    if (oc_close(snaps)<0) ok=0;
    return ok;
}

int oc_transaction_prepare(int root, int data_fd, char *rec[13], const char *phase,
                           const char *before_id, const char *after_id, const char *base_snap,
                           int skip_before_verify, long owner, long group, char nonce_out[33]) {
    if (!oc_equal(rec[1],"active") && !oc_equal(rec[1],"removed")) return 0;
    if (oc_equal(phase,"set") && !oc_deps_equal(data_fd,before_id,after_id)) return 0;
    if (skip_before_verify && oc_deps_equal(data_fd,before_id,after_id)) {
        if (!oc_txn_read_snap(data_fd,after_id,&oc_snap_pool[2])) return 0;
    } else {
        if (!oc_txn_read_snap(data_fd,before_id,&oc_snap_pool[2]) ||
            !oc_txn_read_snap(data_fd,after_id,&oc_snap_pool[3])) return 0;
        if (!oc_targets_match(root,data_fd,before_id,base_snap,owner,group) ||
            !oc_dependencies_pair_match(root,data_fd,before_id,after_id,owner,group)) return 0;
    }
    rec[1]=(char *)phase; rec[6]=(char *)before_id; rec[7]=(char *)after_id;
    return oc_record_write_atomic(root,data_fd,rec,nonce_out);
}

static int oc_stock_pin_ok(int root, oc_u64 stock_dev, int check_stock, const char *path, const char *want_dig) {
    long fd=oc_beneath(root,path[0]=='/'?path+1:path,OC_READ,0);
    char dig[65]; OcMeta m={0};
    int ok=fd>=0 && oc_hash_copy((int)fd,-1,33554432,dig,&m)==OC_COPY_OK &&
        (!check_stock || m.device==stock_dev) && oc_equal(dig,want_dig);
    if (fd>=0 && oc_close((int)fd)<0) ok=0;
    return ok;
}

static int oc_touch_pins_ok(int root) {
    OcMeta stock={0};
    if (!oc_stock_meta(root,&stock)) return 0;
    for (unsigned i=0; i<2; ++i)
        if (!oc_stock_pin_ok(root,stock.device,1,oc_touch_pins[i].path,
                             oc_pin_digest(oc_touch_pins[i].key,oc_touch_pins[i].digest))) return 0;
    return 1;
}

static int oc_vui_plugins_walk(int data_fd, const char *pkg_id, int vdir,
                               int (*cb)(const char *nm, const char *pin, void *ctx), void *ctx) {
    char ppath[128]; OcManifest pmf;
    char *uimod=oc_big_buf, *vlist=oc_big_buf+16384;
    int pdir=oc_join(ppath,sizeof ppath,"packages/",pkg_id)?oc_open_private(data_fd,ppath):-1;
    int ok=pdir>=0 && oc_load_manifest(pdir,pkg_id,oc_mscratch,sizeof oc_mscratch,&pmf) &&
        oc_saved_text(pdir,&pmf,"ui-modules.tsv",uimod,16384) &&
        oc_text(vdir,"vui-plugins.list",vlist,16384,0)>0;
    if (pdir>=0) (void)oc_close(pdir);
    char *p=vlist;
    while (ok && *p) {
        char *nm=p; while (*p && *p!='\n') ++p;
        if (!*p) return 0;
        *p++=0;
        char pin[65];
        ok=oc_lookup_vui_pin(uimod,nm,pin) && cb(nm,pin,ctx);
    }
    return ok;
}

typedef struct { int root; oc_u64 stock_dev; } OcVuiChkCtx;
static int oc_vui_chk_cb(const char *nm, const char *pin, void *raw) {
    OcVuiChkCtx *c=raw; char tp[160];
    return oc_join(tp,sizeof tp,"jci/vui/plugins/",nm) && oc_stock_pin_ok(c->root,c->stock_dev,1,tp,pin);
}

int oc_check_active_pins(int root, int data_fd, const char *pkg_id, const char *snap_id,
                         const char *base_val, const char *touch_val, const char **err_out) {
    if (oc_equal(touch_val,"2") && !oc_touch_pins_ok(root)) {
        *err_out="touch_inputs_changed"; return 0;
    }
    if (!oc_equal(base_val,"1")) return 1;
    OcMeta stock={0};
    if (!oc_stock_meta(root,&stock)) { *err_out="base_inputs_changed"; return 0; }
    for (unsigned i=0; i<5; ++i) {
        if (!oc_stock_pin_ok(root,stock.device,oc_base_pins[i].stock,oc_base_pins[i].path,
                             oc_pin_digest(oc_base_pins[i].key,oc_base_pins[i].digest))) {
            *err_out="base_inputs_changed"; return 0;
        }
    }
    char spath[128];
    int sdir=oc_join(spath,sizeof spath,"snapshots/",snap_id)?oc_open_private(data_fd,spath):-1;
    OcVuiChkCtx vc={root,stock.device};
    int ok=sdir>=0 && oc_vui_plugins_walk(data_fd,pkg_id,sdir,oc_vui_chk_cb,&vc);
    if (sdir>=0) (void)oc_close(sdir);
    if (!ok) { *err_out="base_inputs_changed"; return 0; }
    return 1;
}

static int oc_write_in_row(int fd, const char *k, const char *p, const char *d) {
    char line[384];
    return oc_join4(line,sizeof line,k,"|",p,"|") && oc_join4(line,sizeof line,line,d,"\n",0) &&
        oc_write_all(fd,line,oc_length(line));
}

static int oc_vui_emit_cb(const char *nm, const char *pin, void *raw) {
    char k[128], tp[160];
    return oc_join(k,sizeof k,"base/vui/",nm) && oc_join(tp,sizeof tp,"/jci/vui/plugins/",nm) &&
        oc_write_in_row(*(int *)raw,k,tp,pin);
}

static int oc_seal_after_snap(int root, const char *root_path, int data_fd,
                              const char *snap_id, const char *base_id, const char *pkg_id,
                              long owner, long group, char out_id[65]) {
    if (!oc_join(out_id,65,"",snap_id)) return 0;
    if (oc_equal(pkg_id,"-")) return 1;
    char bs_path[512];
    int bs_st=oc_pkg_boot_select(data_fd,root_path,pkg_id,owner,group,bs_path);
    if (bs_st<=0) return bs_st==0;

    OcTxnSnap *a=&oc_snap_pool[2], *base=&oc_snap_pool[3];
    if (!oc_txn_read_snap(data_fd,snap_id,a) || !a->is_oc2 || !oc_equal(a->pkg,pkg_id) ||
        !oc_txn_read_snap(data_fd,base_id,base)) return 0;

    int snaps=oc_open_private(data_fd,"snapshots");
    if (snaps<0) return 0;

    /* If boot.plan already exists (SHA already verified by oc_txn_read_snap) and validates via boot-select check, keep snap_id. */
    if (oc_digest(&a->mf,"boot.plan")) {
        int sdir=oc_open_private(snaps,snap_id);
        char srel[128], hdr[160], expect_hdr[160];
        long pfd=sdir>=0?oc_openat(sdir,"boot.plan",OC_READ,0):-1;
        int chk_ok=0;
        if (pfd>=0 && oc_join(srel,sizeof srel,OC_DATA "/snapshots/",snap_id) &&
            oc_join4(expect_hdr,sizeof expect_hdr,"OCBP1|",base_id,"|",pkg_id)) {
            char *cargv[]={bs_path,"check",(char *)root_path,srel,0};
            long n=oc_read((int)pfd,hdr,sizeof hdr-1);
            (void)oc_close((int)pfd);
            if (n>0) {
                hdr[n]=0;
                char *nl=hdr; while (*nl && *nl!='\n') ++nl;
                if (*nl=='\n') *nl=0;
                if (oc_equal(hdr,expect_hdr)) {
                    pfd=oc_openat(sdir,"boot.plan",OC_READ,0);
                    if (pfd>=0) {
                        chk_ok=oc_run_cmd_io(bs_path,cargv,(int)pfd,-1,0,0,-1)==0;
                        (void)oc_close((int)pfd);
                    }
                }
            }
        } else if (pfd>=0) (void)oc_close((int)pfd);
        if (sdir>=0) (void)oc_close(sdir);
        if (chk_ok) { (void)oc_close(snaps); return 1; }
    }

    char nonce[33], wleaf[48];
    if (!oc_random(root,nonce) || !oc_join(wleaf,sizeof wleaf,".new-",nonce) ||
        oc_mkdir(snaps,wleaf,0700)<0) { (void)oc_close(snaps); return 0; }
    int wfd=oc_open_private(snaps,wleaf);
    int sdir=oc_open_private(snaps,snap_id);
    int ok=wfd>=0 && sdir>=0;

    const char *mnames[13]; char mdigs[13][65]; unsigned mc=0;
    const char *all[12]={"autostart","config","dependencies","access","runlogin","sshd.conf",
        "selector","sm-normal.conf","sm-wcp.conf","index.html","mmui.xml","vui-plugins.list"};
    for (unsigned i=0; ok && i<12; ++i) {
        if ((i>=3 && i<=5 && !a->has_access) || (i==6 && !a->has_selector)) continue;
        const char *exp=oc_digest(&a->mf,all[i]);
        ok=exp && oc_txn_copy_sync(sdir,all[i],wfd,all[i],mdigs[mc]) && oc_equal(mdigs[mc],exp);
        if (ok) mnames[mc++]=all[i];
    }
    if (sdir>=0 && oc_close(sdir)<0) ok=0;

    long infd=ok?oc_openat(wfd,"inputs",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600):-1;
    if (ok) ok=infd>=0;
    if (ok) {
        char hdr[160];
        ok=oc_join4(hdr,sizeof hdr,"OCBP1|",base_id,"|",pkg_id) && oc_join(hdr,sizeof hdr,hdr,"\n") &&
            oc_write_all((int)infd,hdr,oc_length(hdr));
    }
    /* Dependencies rows */
    if (ok) {
        ok=oc_text(wfd,"dependencies",oc_dep_buf,sizeof oc_dep_buf,0)>=0;
        char *p=oc_dep_buf;
        while (ok && *p) {
            char *ln=p; while (*p && *p!='\n') ++p;
            if (!*p) { ok=0; break; }
            *p++=0;
            const char *dig, *key, *lf; char sc[96], tp[256];
            if (!oc_dep_line_parse(ln,&dig,&key,sc,&lf)) { ok=0; break; }
            if (oc_equal(sc,"root")) {
                const char *rp=oc_root_path_lookup(lf);
                ok=rp && oc_join(tp,sizeof tp,"",rp);
            } else if (oc_prefix(sc,"package-")) {
                ok=oc_join4(tp,sizeof tp,"/" OC_DATA "/packages/",sc+8,"/",lf);
            } else if (oc_prefix(sc,"composed-")) {
                ok=oc_join4(tp,sizeof tp,"/" OC_DATA "/composed/",sc+9,"/",lf);
            } else ok=0;
            if (ok) ok=oc_write_in_row((int)infd,key,tp,dig);
        }
    }
    /* Baseline members + baseline/files.sha256 */
    for (unsigned i=0; ok && i<base->mf.count; ++i) {
        char k[96], tp[256];
        ok=oc_join(k,sizeof k,"baseline/",base->mf.rows[i].name) &&
            oc_join4(tp,sizeof tp,"/" OC_DATA "/snapshots/",base_id,"/",base->mf.rows[i].name) &&
            oc_write_in_row((int)infd,k,tp,base->mf.rows[i].digest);
    }
    if (ok) {
        char tp[256];
        ok=oc_join4(tp,sizeof tp,"/" OC_DATA "/snapshots/",base_id,"/files.sha256",0) &&
            oc_write_in_row((int)infd,"baseline/files.sha256",tp,base_id);
    }
    /* Current members */
    for (unsigned i=0; ok && i<mc; ++i) {
        char k[96], tp[96];
        ok=oc_join(k,sizeof k,"current/",mnames[i]) && oc_join(tp,sizeof tp,"@/",mnames[i]) &&
            oc_write_in_row((int)infd,k,tp,mdigs[i]);
    }
    /* Target autostart, selector, guard/version.ini */
    if (ok) ok=oc_write_in_row((int)infd,"target/autostart","/usr/bin/autostart",a->auto_dig);
    if (ok && !oc_equal(a->sel_hash,"-"))
        ok=oc_write_in_row((int)infd,"target/boot-select","/usr/bin/open-connect-boot-select",a->sel_hash);
    if (ok) {
        char vdig[65]; OcMeta vm={0};
        long vfd=oc_beneath(root,"jci/version.ini",OC_READ,0);
        ok=vfd>=0 && oc_hash_copy((int)vfd,-1,65536,vdig,&vm)==OC_COPY_OK;
        if (vfd>=0 && oc_close((int)vfd)<0) ok=0;
        if (ok) ok=oc_write_in_row((int)infd,"guard/version.ini","/jci/version.ini",vdig);
    }
    if (ok && oc_equal(a->touch,"2")) {
        for (unsigned i=0; ok && i<2; ++i)
            ok=oc_write_in_row((int)infd,oc_touch_pins[i].key,oc_touch_pins[i].path,
                               oc_pin_digest(oc_touch_pins[i].key,oc_touch_pins[i].digest));
    }
    if (ok && oc_equal(a->base,"1")) {
        for (unsigned i=0; ok && i<5; ++i)
            ok=oc_write_in_row((int)infd,oc_base_pins[i].key,oc_base_pins[i].path,
                               oc_pin_digest(oc_base_pins[i].key,oc_base_pins[i].digest));
        int ifd=(int)infd;
        if (ok) ok=oc_vui_plugins_walk(data_fd,pkg_id,wfd,oc_vui_emit_cb,&ifd);
    }
    if (ok && a->has_access) {
        ok=oc_write_in_row((int)infd,"target/runlogin","/usr/bin/runlogin",a->login_dig) &&
            oc_write_in_row((int)infd,"target/sshd.conf","/etc/ssh/sshd_config",a->ssh_dig);
        if (ok && !oc_equal(a->acc_f[5],"-")) {
            char hrel[96], habs[96];
            ok=oc_join(hrel,sizeof hrel,"usr/bin/.open-connect-runlogin-",a->acc_f[5]) &&
                oc_join(habs,sizeof habs,"/",hrel) &&
                oc_write_in_row((int)infd,"hold/runlogin",habs,oc_absent_at(root,hrel)?"-":base->login_dig);
        }
        if (ok && !oc_equal(a->acc_f[2],"-")) {
            char kp[256];
            ok=oc_access_key_verify(data_fd,a->acc_f[2],owner,group) &&
                oc_join4(kp,sizeof kp,"/" OC_DATA "/keys/",a->acc_f[2],".cmu",0) &&
                oc_write_in_row((int)infd,"key/owner",kp,a->acc_f[2]);
        }
    }
    if (infd>=0 && oc_close((int)infd)<0) ok=0;

    /* Run boot-select seal <root_path> <OC_DATA>/snapshots/<wleaf>. */
    if (ok) {
        long in_rd=oc_openat(wfd,"inputs",OC_READ,0);
        long pl_wr=oc_openat(wfd,"boot.plan",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        char wrel[128];
        ok=in_rd>=0 && pl_wr>=0 && oc_join(wrel,sizeof wrel,OC_DATA "/snapshots/",wleaf);
        if (ok) {
            char *sargv[]={bs_path,"seal",(char *)root_path,wrel,0};
            ok=oc_run_cmd_io(bs_path,sargv,(int)in_rd,(int)pl_wr,0,0,-1)==0 &&
                oc_mode((int)pl_wr,0600)>=0 && oc_sync((int)pl_wr)>=0;
        }
        if (in_rd>=0) (void)oc_close((int)in_rd);
        if (pl_wr>=0 && oc_close((int)pl_wr)<0) ok=0;
        if (oc_unlink(wfd,"inputs")<0) ok=0;
        OcMeta pm={0};
        if (ok) ok=oc_hash_file_at(wfd,"boot.plan",mdigs[mc],&pm);
        if (ok) mnames[mc++]="boot.plan";
    }
    if (ok) ok=oc_finish_snapshot_dir(data_fd,snaps,wfd,wleaf,mnames,mdigs,mc,out_id);
    else { if (wfd>=0) (void)oc_close(wfd); oc_rm_subdir(snaps,wleaf); }
    if (oc_close(snaps)<0) ok=0;
    return ok;
}

int oc_transaction_reconcile(int root, const char *root_path, int data_fd, char *rec[13],
                             const char *session_dir, const char *prepared_rev,
                             long owner, long group, const char **err_out) {
    if (oc_equal(rec[1],"active") || oc_equal(rec[1],"removed")) return 1;
    char phase_buf[16], before_id[65], after_id[65], rev_buf[33], base_id[65];
    if (!oc_join(phase_buf,sizeof phase_buf,"",rec[1]) ||
        !oc_join(before_id,sizeof before_id,"",rec[6]) ||
        !oc_join(after_id,sizeof after_id,"",rec[7]) ||
        !oc_join(rev_buf,sizeof rev_buf,"",rec[2]) ||
        !oc_join(base_id,sizeof base_id,"",rec[4])) { *err_out="invalid_record"; return 0; }
    int is_uninstall=oc_equal(phase_buf,"uninstall");
    if (is_uninstall) {
        if (!oc_equal(before_id,rec[5]) || !oc_uninstall_owned(data_fd,before_id,base_id,owner,group)) {
            *err_out="state_changed"; return 0;
        }
    }
    OcTxnSnap *b=&oc_snap_pool[0], *a=&oc_snap_pool[1];
    if (!oc_txn_read_snap(data_fd,before_id,b)) { *err_out="invalid_before"; return 0; }
    if (!oc_txn_read_snap(data_fd,after_id,a)) { *err_out="invalid_after"; return 0; }
    int same_prep=prepared_rev && *prepared_rev && oc_equal(prepared_rev,rev_buf);
    if (!same_prep) {
        if (!oc_dependencies_pair_match(root,data_fd,before_id,after_id,owner,group) || oc_sync(data_fd)<0) {
            *err_out="dependencies_changed"; return 0;
        }
    }
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    char act_h[65], act_m[40], act_nv[16]; OcMeta am={0};
    int aok=ubin>=0 && oc_hash_file_at((int)ubin,"autostart",act_h,&am) && oc_meta_mode_str(&am,act_m);
    if (ubin>=0 && oc_close((int)ubin)<0) aok=0;
    if (!aok) { *err_out="startup_changed"; return 0; }
    if (!oc_nvram_at(root,act_nv)) { *err_out="nvram_unreadable"; return 0; }
    if (!((oc_equal(act_h,b->auto_dig)&&oc_equal(act_m,b->meta)) ||
          (oc_equal(act_h,a->auto_dig)&&oc_equal(act_m,a->meta)))) { *err_out="startup_changed"; return 0; }
    if (!oc_equal(act_nv,b->nvram) && !oc_equal(act_nv,a->nvram)) { *err_out="nvram_changed"; return 0; }
    if ((b->has_access || a->has_access) && !oc_access_pair_check(root,data_fd,before_id,after_id,base_id,owner,group)) {
        *err_out="access_changed"; return 0;
    }
    int sel_pair=b->has_selector || a->has_selector;
    if (sel_pair && !oc_selector_pair_check(root,data_fd,before_id,after_id,owner,group)) {
        *err_out="selector_changed"; return 0;
    }
    if ((oc_equal(phase_buf,"set") || oc_equal(phase_buf,"install")) &&
        oc_equal(a->touch,"2") && !oc_touch_pins_ok(root)) {
        if (!oc_startup_staging_retire(root,root_path,data_fd,rev_buf,after_id,base_id,owner,group)) {
            *err_out="startup_stage_changed"; return 0;
        }
        char new_rev[33], new_after[65];
        char *rb_rec[13];
        for (unsigned i=0; i<13; ++i) rb_rec[i]=rec[i];
        if (oc_equal(phase_buf,"set") && !oc_equal(b->touch,"2")) {
            rb_rec[6]=after_id; rb_rec[7]=before_id;
        } else {
            char apath[128], cfg[1024], dnonce[33], dleaf[48], dbase[320], cfg_abs[400];
            if (!oc_join(apath,sizeof apath,"snapshots/",after_id)) { *err_out="plan_failed"; return 0; }
            int adir=oc_open_private(data_fd,apath);
            int cok=adir>=0 && oc_text(adir,"config",cfg,sizeof cfg,0)>0;
            char *pos=0;
            if (cok) {
                for (char *p=cfg; *p; ++p) if (oc_prefix(p,"\ntouch=2\n")) { pos=p+7; break; }
            }
            if (!pos) { if (adir>=0) (void)oc_close(adir); *err_out="invalid_preferences"; return 0; }
            *pos='0';
            if (!oc_random(root,dnonce) || !oc_join(dleaf,sizeof dleaf,".downgrade-",dnonce) ||
                oc_mkdir(data_fd,dleaf,0700)<0) { (void)oc_close(adir); *err_out="plan_failed"; return 0; }
            int dwfd=oc_open_private(data_fd,dleaf);
            cok=dwfd>=0 && oc_new_text(dwfd,"config",cfg,0600) &&
                oc_data_base(root_path,dbase,sizeof dbase) &&
                oc_join4(cfg_abs,sizeof cfg_abs,dbase,"/",dleaf,"/config");
            const char *keep[7]={"access","runlogin","sshd.conf","selector",
                "index.html","mmui.xml","vui-plugins.list"};
            for (unsigned i=0; cok && i<7; ++i) {
                if (oc_absent_at(adir,keep[i])) continue;
                cok=oc_copy_file_at(adir,keep[i],dwfd,keep[i],0600,1,0,0);
            }
            (void)oc_close(adir);
            if (cok) cok=oc_render_sm_profiles(data_fd,root_path,a->pkg,after_id,cfg_abs,
                                               oc_length(cfg),a->warning,dwfd) &&
                oc_snapshot_create(root,data_fd,after_id,a->pkg,a->nvram,a->meta,after_id,
                                   dwfd,cfg,session_dir,root_path,owner,group,new_after);
            if (dwfd>=0) (void)oc_close(dwfd);
            oc_rm_subdir(data_fd,dleaf);
            if (!cok) { *err_out="plan_failed"; return 0; }
            rb_rec[7]=new_after;
        }
        if (!oc_record_write_atomic(root,data_fd,rb_rec,new_rev)) { *err_out="record_rename_failed"; return 0; }
        rb_rec[2]=new_rev;
        return oc_transaction_reconcile(root,root_path,data_fd,rb_rec,session_dir,0,owner,group,err_out);
    }

    char auto_src[128];
    if (!oc_join4(auto_src,sizeof auto_src,"snapshots/",after_id,"/autostart",0)) { *err_out="plan_failed"; return 0; }
    if (!is_uninstall) {
        if (sel_pair) {
            char stg[96];
            int skip_sel=same_prep && oc_equal(phase_buf,"set") &&
                oc_equal(b->sel_hash,a->sel_hash) && oc_equal(b->sel_meta,a->sel_meta) &&
                oc_equal(b->sel_pkg,a->sel_pkg) &&
                oc_join(stg,sizeof stg,"usr/bin/.open-connect-",rev_buf) &&
                oc_join(stg,sizeof stg,stg,"-open-connect-boot-select") &&
                oc_absent_at(root,stg) && oc_mounts_mode(root,oc_mscratch,sizeof oc_mscratch,0);
            if (!skip_sel && !oc_selector_apply(root,root_path,data_fd,rev_buf,before_id,after_id,base_id,owner,group)) {
                *err_out="selector_apply_failed"; return 0;
            }
        }
        if (!oc_root_publish(root,root_path,data_fd,rev_buf,"usr/bin/autostart",auto_src,a->meta,
                             act_h,act_m,0,0,0,base_id,owner,group)) {
            *err_out="startup_publish_failed"; return 0;
        }
    }
    if (a->has_access &&
        !oc_access_pair_apply(root,root_path,data_fd,rev_buf,before_id,after_id,base_id,same_prep,owner,group)) {
        *err_out="access_apply_failed"; return 0;
    }
    if (!oc_equal(b->nvram,a->nvram) && !oc_nvram_change(root,act_nv,a->nvram)) {
        *err_out="nvram_commit_failed"; return 0;
    }
    if (is_uninstall) {
        if (!oc_root_publish(root,root_path,data_fd,rev_buf,"usr/bin/autostart",auto_src,a->meta,
                             act_h,act_m,0,0,0,base_id,owner,group)) {
            *err_out="startup_publish_failed"; return 0;
        }
        if (a->has_access && !oc_access_hold_cleanup(root,root_path,data_fd,base_id,owner,group)) {
            *err_out="access_cleanup_failed"; return 0;
        }
        if (sel_pair && !oc_selector_apply(root,root_path,data_fd,rev_buf,before_id,after_id,base_id,owner,group)) {
            *err_out="selector_remove_failed"; return 0;
        }
    }
    if (sel_pair && !oc_selector_pair_check(root,data_fd,after_id,after_id,owner,group)) {
        *err_out="selector_verification_failed"; return 0;
    }
    if (!oc_targets_match(root,data_fd,after_id,base_id,owner,group) ||
        !oc_dependencies_match(root,data_fd,after_id,owner,group)) {
        *err_out="final_verification_failed"; return 0;
    }
    char sealed_id[65];
    if (!is_uninstall && !oc_equal(a->pkg,"-")) {
        if (!oc_equal(a->pkg,rec[3]) ||
            !oc_seal_after_snap(root,root_path,data_fd,after_id,base_id,rec[3],owner,group,sealed_id)) {
            *err_out="boot_snapshot_failed"; return 0;
        }
    } else {
        (void)oc_join(sealed_id,sizeof sealed_id,"",after_id);
    }

    char *fin[13];
    for (unsigned i=0; i<13; ++i) fin[i]=rec[i];
    fin[5]=sealed_id;
    if (is_uninstall) { fin[1]="removed"; fin[12]="removed"; fin[9]="0"; }
    else if (oc_equal(phase_buf,"install")) { fin[1]="active"; fin[12]="installed"; fin[9]="3"; }
    else if (oc_equal(phase_buf,"set")) { fin[1]="active"; fin[12]="restart"; fin[9]="3"; }
    else { fin[1]="active"; }
    fin[6]="-"; fin[7]="-"; fin[8]="-";
    if (!oc_equal(phase_buf,"apply")) { fin[10]="-"; fin[11]="-"; }
    if (!oc_record_write_atomic(root,data_fd,fin,0)) { *err_out="record_rename_failed"; return 0; }
    return 1;
}

int oc_uninstall_cleanup(int root, const char *root_path, int data_fd, const char *session_dir,
                         long owner, long group, const char **err_out) {
    char dbase[320], dpref[324];
    if (!oc_data_base(root_path,dbase,sizeof dbase) || !oc_join(dpref,sizeof dpref,dbase,"/")) {
        *err_out="invalid_state_directory"; return 0;
    }
    if (oc_equal(session_dir,dbase) || oc_prefix(session_dir,dpref)) {
        *err_out="cleanup_requires_ram"; return 0;
    }
    if (!oc_mounts_mode(root,oc_mscratch,sizeof oc_mscratch,0)) { *err_out="root_mount_changed"; return 0; }
    if (oc_mounts_has(root,dbase,0,1)!=0) { *err_out="cleanup_mount_present"; return 0; }

    char parent_abs[320]; unsigned plen=oc_length(dbase), slash=0;
    for (unsigned i=0; i<plen; ++i) if (dbase[i]=='/') slash=i;
    if (!slash || slash+1>=plen) { *err_out="invalid_state_directory"; return 0; }
    for (unsigned i=0; i<slash; ++i) parent_abs[i]=dbase[i];
    parent_abs[slash]=0;
    const char *dleaf=dbase+slash+1;
    long pdir=oc_openat(OC_CWD,parent_abs,OC_DIRECTORY,0);
    if (pdir<0) { *err_out="invalid_state_directory"; return 0; }

    if (oc_absent_at(data_fd,"record")) {
        int ok=oc_rmdirat((int)pdir,dleaf)>=0 && oc_sync((int)pdir)>=0;
        (void)oc_close((int)pdir);
        if (!ok) { *err_out="invalid_cleanup_state"; return 0; }
        return 1;
    }
    char rec_buf[1024], *rec[13];
    if (!oc_record_read_any(data_fd,owner,group,rec_buf,sizeof rec_buf,rec)) {
        (void)oc_close((int)pdir); *err_out="invalid_record"; return 0;
    }
    if (oc_equal(rec[1],"removed")) {
        if (!oc_targets_match(root,data_fd,rec[5],rec[4],owner,group) ||
            !oc_dependencies_match(root,data_fd,rec[5],owner,group)) {
            (void)oc_close((int)pdir); *err_out="state_changed"; return 0;
        }
        if (!oc_startup_staging_guard(root)) {
            (void)oc_close((int)pdir); *err_out="startup_stage_changed"; return 0;
        }
        rec[1]="purge";
        if (!oc_record_write_atomic(root,data_fd,rec,0)) {
            (void)oc_close((int)pdir); *err_out="record_rename_failed"; return 0;
        }
    } else if (!oc_equal(rec[1],"purge")) {
        (void)oc_close((int)pdir); *err_out="not_removed"; return 0;
    }
    OcMeta dm={0};
    if (oc_stat(data_fd,&dm)<0) { (void)oc_close((int)pdir); *err_out="cleanup_failed"; return 0; }
    if (!oc_rm_tree_cb_cleanup(data_fd,dm.device,"record",0) ||
        oc_sync(data_fd)<0 || oc_unlink(data_fd,"record")<0 || oc_sync(data_fd)<0 ||
        oc_rmdirat((int)pdir,dleaf)<0 || oc_sync((int)pdir)<0) {
        (void)oc_close((int)pdir); *err_out="cleanup_failed"; return 0;
    }
    (void)oc_close((int)pdir);
    return 1;
}
