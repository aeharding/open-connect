/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Snapshot auditing, independent-copy sealing/publication, and bounded
 * crash-safe tombstone garbage collection of unreachable snapshots.
 */
#include "oc-core.h"

static OcPub oc_pub;

int oc_audit_load(OcBoot *b, const char *root_path, const char *expected_current, const char *candidate, int allow_touch_drift) {
    b->root=b->data=b->ram=b->lock=b->snapshot=b->baseline=b->package=b->composed=b->stage=b->observer=b->log=-1;
    b->gated=0; b->metadata_drift=0; b->touch_drift=allow_touch_drift?1:0; b->input_count=0;
    b->owner=oc_owner(); b->group=oc_group();
    b->root=(int)oc_openat(OC_CWD,root_path,OC_DIRECTORY,0);
    if (b->root<0) return 0;
    b->data=oc_open_private(b->root,OC_DATA);
    if (b->data<0) return 0;
    if (!oc_record_file(b,expected_current,candidate)) return 0;
    if (candidate) b->record_fields[5]=(char *)candidate;
    if (!oc_mounts(b)||!oc_policy_load(b)) return 0;
    char nvram[16];
    if (!oc_nvram(b,nvram)||!oc_equal(nvram,b->flags[3])) return 0;
    if (candidate) {
        const char *wanted=oc_equal(b->flags[1],"1")?"disable":b->base_flags[3];
        if (!oc_equal(wanted,b->flags[3])) return 0;
    }
    return oc_load(b) && !b->metadata_drift;
}

int oc_audit(const char *root_path, const char *expected_current, const char *candidate) {
    int ok=oc_audit_load(&oc_boot,root_path,expected_current,candidate,0);
    oc_close_boot(&oc_boot);
    if (oc_boot.root>=0 && oc_close(oc_boot.root)<0) ok=0;
    return ok?0:1;
}

static int oc_copy_verified_member(OcBoot *b, int dst_dir, const char *name, const char *expected_digest, char out_digest[65], OcMeta *out_meta) {
    if (!expected_digest) return 0;
    long src=oc_openat(b->snapshot,name,OC_READ,0);
    if (src<0) return 0;
    long dst=oc_openat(dst_dir,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (dst<0) { (void)oc_close((int)src); return 0; }
    OcMeta sm;
    int ok=oc_hash_copy((int)src,(int)dst,33554432,out_digest,&sm)==OC_COPY_OK &&
        oc_equal(out_digest,expected_digest) && oc_mode((int)dst,0600)>=0 &&
        oc_sync((int)dst)>=0 && oc_stat((int)dst,out_meta)>=0 &&
        out_meta->mode==(OC_REGULAR|0600) && out_meta->uid==(unsigned)b->owner && out_meta->gid==(unsigned)b->group;
    if (oc_close((int)src)<0) ok=0;
    if (oc_close((int)dst)<0) ok=0;
    return ok;
}

static int oc_emit_plan_row(int fd, const char *key, const char *path, const char *digest, const OcMeta *m, int absent) {
    char meta[131];
    if (!oc_write_all(fd,key,oc_length(key))||!oc_write_all(fd,"|",1)||
        !oc_write_all(fd,path,oc_length(path))||!oc_write_all(fd,"|",1)||
        !oc_write_all(fd,digest,oc_length(digest))) return 0;
    if (absent) return oc_write_all(fd,"|-|-|-|-|-|-|-|-|-|-\n",21);
    unsigned n=oc_meta_text(meta,m);
    return oc_write_all(fd,meta,n)&&oc_write_all(fd,"\n",1);
}

static int oc_emit_external_pin(int plan_fd, OcBoot *b, const char *key, const char *path, const char *digest, int stock_req) {
    OcInput *old=oc_find(b,key);
    if (old && !old->absent && oc_equal(old->path,path) && oc_equal(old->digest,digest)) {
        if (stock_req) {
            OcMeta stock;
            if (!oc_stock_meta(b->root,&stock)) return 2;
            if (old->meta.device!=stock.device) return 1;
        }
        return oc_emit_plan_row(plan_fd,key,path,digest,&old->meta,0)?0:2;
    }
    long fd=oc_beneath(b->root,path+1,OC_READ,0);
    if (fd<0) return fd==-2?1:2;
    char got[65]; OcMeta cur;
    int copied=oc_hash_copy((int)fd,-1,33554432,got,&cur);
    int closed=oc_close((int)fd)>=0;
    if (copied!=OC_COPY_OK||!closed) return 2;
    if (!oc_equal(got,digest)) return 1;
    if (stock_req) {
        OcMeta stock;
        if (!oc_stock_meta(b->root,&stock)) return 2;
        if (cur.device!=stock.device) return 1;
    }
    return oc_emit_plan_row(plan_fd,key,path,digest,&cur,0)?0:2;
}

int oc_seal_publish(const char *root_path, const char *expected_current, const char *work_rel, const char *expected_nvram) {
    OcBoot *b=&oc_boot;
    const char *prefix=OC_DATA "/snapshots/.new-";
    if (!oc_prefix(work_rel,prefix)) return 1;
    const char *work_leaf=work_rel+oc_length(OC_DATA "/snapshots/");
    for (const char *p=work_leaf; *p; ++p) if (*p=='/') return 1;
    if (!oc_key(work_leaf)||(expected_nvram&&!oc_nvram_value(expected_nvram))) return 1;
    int err_rc=1;
    int ok=oc_audit_load(b,root_path,expected_current,0,1);
    long work=-1, snaps=-1, plan_fd=-1, mf_fd=-1;
    char snap_id[65]; snap_id[0]=0;
    if (ok) {
        long orig_mmui=oc_beneath(b->data,"originals/mmui.xml",OC_READ,0);
        char mm_d[65]; OcMeta mm_m;
        ok=orig_mmui>=0 && oc_hash_copy((int)orig_mmui,-1,33554432,mm_d,&mm_m)==OC_COPY_OK &&
            oc_equal(mm_d,oc_pin_digest("originals/mmui.xml","ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0"));
        if (orig_mmui>=0 && oc_close((int)orig_mmui)<0) ok=0;
    }
    if (ok) {
        work=oc_open_private(b->root,work_rel);
        ok=work>=0 && oc_absent_at((int)work,"files.sha256") && oc_absent_at((int)work,"boot.plan");
    }
    const char *members[12]; unsigned mcount=0;
    members[mcount++]="autostart"; members[mcount++]="config"; members[mcount++]="dependencies";
    if (b->access_present) { members[mcount++]="access"; members[mcount++]="runlogin"; members[mcount++]="sshd.conf"; }
    unsigned sel_idx=mcount; members[mcount++]="selector";
    unsigned prof_idx=mcount;
    members[mcount++]="sm-normal.conf"; members[mcount++]="sm-wcp.conf";
    members[mcount++]="index.html"; members[mcount++]="mmui.xml";
    unsigned vui_idx=mcount; members[mcount++]="vui-plugins.list";
    OcManifest work_allowed; work_allowed.count=6;
    const char *allowed_names[6]={"config","sm-normal.conf","sm-wcp.conf","index.html","mmui.xml","vui-plugins.list"};
    for (unsigned i=0; i<6; ++i) { work_allowed.rows[i].name=(char *)allowed_names[i]; work_allowed.rows[i].digest=(char *)""; }
    if (ok) ok=oc_members((int)work,&work_allowed,2);
    char *new_flags[9], new_svc[65];
    if (ok) {
        long cfd=oc_openat((int)work,"config",OC_READ,0);
        ok=cfd>=0 && oc_hash_copy((int)cfd,-1,33554432,oc_pub.m_digest[1],&oc_pub.m_meta[1])==OC_COPY_OK &&
            oc_pub.m_meta[1].mode==(OC_REGULAR|0600) && oc_pub.m_meta[1].uid==(unsigned)b->owner &&
            oc_pub.m_meta[1].gid==(unsigned)b->group && oc_sync((int)cfd)>=0;
        if (cfd>=0 && oc_close((int)cfd)<0) ok=0;
    }
    if (ok) {
        ok=oc_verified_text((int)work,"config",oc_pub.m_digest[1],oc_pub.new_cfg,sizeof oc_pub.new_cfg) &&
            oc_prefix(oc_pub.new_cfg,"OC2\n") && oc_config(b,oc_pub.new_cfg,new_flags,1,new_svc) &&
            oc_equal(new_flags[0],b->record_fields[3]) && oc_equal(new_flags[4],b->flags[4]);
        if (ok) {
            const char *wanted=oc_equal(new_flags[1],"1")?"disable":b->base_flags[3];
            const char *req_nv=expected_nvram?expected_nvram:b->flags[3];
            if (!oc_equal(wanted,new_flags[3])||!oc_equal(new_flags[3],req_nv)) ok=0;
        }
    }
    if (ok && (b->touch_drift&2)) {
        err_rc=oc_equal(new_flags[1],"2")?92:OC_SLOW;
        ok=0;
    }
    int same_svc=ok&&oc_equal(b->svc_digest,new_svc);
    int same_w=ok&&oc_equal(b->flags[2],new_flags[2]);
    int same_b=ok&&oc_equal(b->flags[6],new_flags[6]);
    int same_wl=ok&&oc_equal(b->flags[7],new_flags[7]);
    int same_t2=ok&&(oc_equal(b->flags[1],"2")==oc_equal(new_flags[1],"2"));
    int same_as=ok&&oc_equal(b->flags[8],new_flags[8]);
    int reuse[5]={
        same_t2&&same_w&&same_b&&same_wl&&same_svc,
        same_t2&&same_w&&same_b&&same_wl&&same_svc,
        same_w&&same_b&&same_svc&&same_as,
        same_w&&same_b&&same_svc,
        same_b&&same_svc
    };
    if (ok) {
        const char *st=oc_equal(new_flags[2],"1")?"on":"off";
        const char *tpl[3]={oc_equal(st,"on")?"sm-normal-on.conf":"sm-normal-off.conf",
            oc_equal(st,"on")?"sm-wcp-on.conf":"sm-wcp-off.conf",
            oc_equal(st,"on")?"index-on.html":"index-off.html"};
        for (unsigned i=0; ok&&i<3; ++i) if (!oc_absent_at((int)work,members[prof_idx+i])) {
            long tfd=oc_openat(b->composed,tpl[i],OC_READ,0);
            char td[65]; OcMeta tm;
            const char *exp=oc_digest(&b->composition,tpl[i]);
            ok=tfd>=0 && exp && oc_hash_copy((int)tfd,-1,33554432,td,&tm)==OC_COPY_OK && oc_equal(td,exp);
            if (tfd>=0 && oc_close((int)tfd)<0) ok=0;
        }
    }
    for (unsigned i=0; ok&&i<mcount; ++i) {
        if (i==1) continue;
        if (i<=sel_idx) {
            ok=oc_copy_verified_member(b,(int)work,members[i],oc_digest(&b->current,members[i]),oc_pub.m_digest[i],&oc_pub.m_meta[i]);
        } else if (oc_absent_at((int)work,members[i])) {
            ok=reuse[i-prof_idx] &&
                oc_copy_verified_member(b,(int)work,members[i],oc_digest(&b->current,members[i]),oc_pub.m_digest[i],&oc_pub.m_meta[i]);
        } else {
            long fd=oc_openat((int)work,members[i],OC_READ,0);
            if (fd<0) { ok=0; break; }
            ok=oc_hash_copy((int)fd,-1,33554432,oc_pub.m_digest[i],&oc_pub.m_meta[i])==OC_COPY_OK &&
                oc_pub.m_meta[i].mode==(OC_REGULAR|0600) && oc_pub.m_meta[i].uid==(unsigned)b->owner &&
                oc_pub.m_meta[i].gid==(unsigned)b->group && oc_sync((int)fd)>=0;
            if (oc_close((int)fd)<0) ok=0;
            if (ok && reuse[i-prof_idx]) {
                const char *prev_d=oc_digest(&b->current,members[i]);
                if (!prev_d||!oc_equal(oc_pub.m_digest[i],prev_d)) ok=0;
            }
        }
    }
    if (ok) {
        plan_fd=oc_openat((int)work,"boot.plan",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        ok=plan_fd>=0 &&
            oc_write_all((int)plan_fd,"OCBP1|",6) &&
            oc_write_all((int)plan_fd,b->record_fields[4],64) &&
            oc_write_all((int)plan_fd,"|",1) &&
            oc_write_all((int)plan_fd,b->record_fields[3],64) &&
            oc_write_all((int)plan_fd,"\n",1);
    }
    for (unsigned i=0; ok&&i<b->input_count; ++i) {
        OcInput *row=&b->inputs[i];
        if (oc_prefix(row->key,"current/")||oc_prefix(row->key,"touch/devices/")||oc_prefix(row->key,"base/")) continue;
        ok=oc_emit_plan_row((int)plan_fd,row->key,row->path,row->digest,&row->meta,row->absent);
    }
    for (unsigned i=0; ok&&i<mcount; ++i) {
        char key[192], path[192];
        ok=oc_join(key,sizeof key,"current/",members[i]) &&
            oc_join(path,sizeof path,"@/",members[i]) &&
            oc_emit_plan_row((int)plan_fd,key,path,oc_pub.m_digest[i],&oc_pub.m_meta[i],0);
    }
    if (ok && oc_equal(new_flags[1],"2")) {
        for (unsigned i=0; ok&&i<2; ++i) {
            int pr=oc_emit_external_pin((int)plan_fd,b,oc_touch_pins[i].key,oc_touch_pins[i].path,
                                        oc_pin_digest(oc_touch_pins[i].key,oc_touch_pins[i].digest),1);
            if (pr) { err_rc=pr==1?92:1; ok=0; }
        }
    }
    if (ok) ok=oc_verified_text((int)work,"vui-plugins.list",oc_pub.m_digest[vui_idx],oc_pub.vui_list,sizeof oc_pub.vui_list);
    if (ok && oc_equal(new_flags[6],"1")) {
        for (unsigned i=0; ok&&i<5; ++i) {
            int pr=oc_emit_external_pin((int)plan_fd,b,oc_base_pins[i].key,oc_base_pins[i].path,
                                        oc_pin_digest(oc_base_pins[i].key,oc_base_pins[i].digest),oc_base_pins[i].stock);
            if (pr) { err_rc=pr==1?93:1; ok=0; }
        }
        if (ok) ok=oc_saved_text(b->package,&b->pkg,"ui-modules.tsv",b->scratch,sizeof b->scratch);
        char *p=oc_pub.vui_list; unsigned vcount=0;
        while (ok && *p) {
            char *name=p;
            while (*p && *p!='\n') ++p;
            if (!*p) { ok=0; break; }
            *p++=0;
            if (!oc_key(name)||vcount==48||oc_length(name)>=64) { ok=0; break; }
            for (const char *q=name; *q; ++q) if (*q=='/') ok=0;
            for (unsigned j=0; ok&&j<vcount; ++j) if (oc_equal(oc_pub.seen_v[j],name)) ok=0;
            if (!ok) break;
            for (unsigned j=0;; ++j) { oc_pub.seen_v[vcount][j]=name[j]; if (!name[j]) break; }
            ++vcount;
            char pin[65], key[192], path[192];
            if (!oc_lookup_vui_pin(b->scratch,name,pin) ||
                !oc_join(key,sizeof key,"base/vui/",name) ||
                !oc_join(path,sizeof path,"/jci/vui/plugins/",name)) { err_rc=93; ok=0; break; }
            int pr=oc_emit_external_pin((int)plan_fd,b,key,path,pin,1);
            if (pr) { err_rc=pr==1?93:1; ok=0; }
        }
        if (ok && vcount<36) ok=0;
    } else if (ok && oc_pub.vui_list[0]!=0) ok=0;
    if (plan_fd>=0) {
        if (ok) ok=oc_mode((int)plan_fd,0600)>=0 && oc_sync((int)plan_fd)>=0;
        if (oc_close((int)plan_fd)<0) ok=0;
    }
    char plan_digest[65]; OcMeta plan_meta;
    if (ok) {
        long pfd=oc_openat((int)work,"boot.plan",OC_READ,0);
        ok=pfd>=0 && oc_hash_copy((int)pfd,-1,OC_PLAN_LIMIT,plan_digest,&plan_meta)==OC_COPY_OK;
        if (pfd>=0 && oc_close((int)pfd)<0) ok=0;
    }
    if (ok) {
        mf_fd=oc_openat((int)work,"files.sha256",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        ok=mf_fd>=0;
        OcHash h; oc_hash_init(&h);
        for (unsigned i=0; ok&&i<=mcount; ++i) {
            const char *dig=i<mcount?oc_pub.m_digest[i]:plan_digest;
            const char *nm=i<mcount?members[i]:"boot.plan";
            char row[192];
            ok=oc_join(row,sizeof row,dig,"  ") && oc_join(row,sizeof row,row,nm) && oc_join(row,sizeof row,row,"\n");
            if (ok) {
                unsigned rlen=oc_length(row);
                oc_hash_add(&h,row,rlen);
                ok=oc_write_all((int)mf_fd,row,rlen);
            }
        }
        if (ok) {
            oc_hash_finish(&h,snap_id);
            ok=oc_mode((int)mf_fd,0600)>=0 && oc_sync((int)mf_fd)>=0;
        }
        if (mf_fd>=0 && oc_close((int)mf_fd)<0) ok=0;
        if (ok) ok=oc_sync((int)work)>=0;
    }
    if (work>=0 && oc_close((int)work)<0) ok=0;
    work=-1;
    if (ok) {
        snaps=oc_open_private(b->data,"snapshots");
        ok=snaps>=0 && oc_absent_at((int)snaps,snap_id) && oc_rename((int)snaps,work_leaf,snap_id)>=0 && oc_sync((int)snaps)>=0;
    }
    if (snaps>=0 && oc_close((int)snaps)<0) ok=0;
    oc_close_boot(b);
    if (b->root>=0 && oc_close(b->root)<0) ok=0;
    if (ok) ok=oc_write_all(1,snap_id,64) && oc_write_all(1,"\n",1);
    else (void)oc_write_all(2,"boot_plan_refused\n",18);
    return ok?0:err_rc;
}

/* Safe bounded unreachable-snapshot GC:
 * - Verifies inherited lock fd (no flock self-deadlock) or acquires lock standalone.
 * - Requires settled active OC1 with R_BEFORE=-, R_AFTER=-, legacy_undo=-.
 * - Pins R_BASE, R_CURRENT, and independently validated live selected/access-selected.
 * - Resumes .prune-* tombstones first; unlinks non-manifest leaves before files.sha256.
 */
static int oc_snap_leaf_allowed(const char *name) {
    static const char *const allowed[]={
        "autostart","config","dependencies","access","runlogin","sshd.conf",
        "selector","sm-normal.conf","sm-wcp.conf","index.html","mmui.xml",
        "vui-plugins.list","boot.plan"
    };
    for (unsigned i=0; i<sizeof allowed/sizeof *allowed; ++i)
        if (oc_equal(name,allowed[i])) return 1;
    return 0;
}

typedef struct {
    int dir_fd;
    oc_u64 snaps_dev;
    OcManifest *mf;
    char leaves[16][32];
    unsigned count;
    int saw_manifest;
} OcGcLeafCtx;

static int oc_gc_leaf_cb(const char *name, void *raw) {
    OcGcLeafCtx *c=raw;
    OcMeta m;
    if (oc_metadata(c->dir_fd,name,&m)<0 || (m.mode&OC_TYPE)!=OC_REGULAR || m.device!=c->snaps_dev) return -1;
    if (oc_equal(name,"files.sha256")) { c->saw_manifest=1; return 1; }
    if (!c->mf || !oc_digest(c->mf,name) || !oc_snap_leaf_allowed(name)) return -1;
    if (c->count>=16 || !oc_join(c->leaves[c->count],sizeof c->leaves[0],"",name)) return -1;
    ++c->count;
    return 1;
}

static int oc_gc_empty_cb(const char *name, void *raw) {
    (void)name; *(int *)raw=1; return 0;
}

/* Returns 0=not actionable, 1=empty (manifest absent), 2=manifest+leaves valid in lctx. */
static int oc_gc_inspect_tombstone(int tdir, oc_u64 snaps_dev, const char *id, char mf_buf[4096], OcManifest *mf, OcGcLeafCtx *lctx) {
    OcMeta tm;
    if (oc_stat(tdir,&tm)<0 || tm.device!=snaps_dev) return 0;
    if (oc_absent_at(tdir,"files.sha256")) {
        int nonempty=0;
        return oc_dir_iter(tdir,oc_gc_empty_cb,&nonempty) && !nonempty ? 1 : 0;
    }
    if (!oc_verified_text(tdir,"files.sha256",id,mf_buf,4096) || !oc_manifest(mf_buf,mf,0)) return 0;
    for (unsigned i=0; i<mf->count; ++i)
        if (!oc_snap_leaf_allowed(mf->rows[i].name)) return 0;
    lctx->dir_fd=tdir; lctx->snaps_dev=snaps_dev; lctx->mf=mf; lctx->count=0; lctx->saw_manifest=0;
    return oc_dir_iter(tdir,oc_gc_leaf_cb,lctx) && lctx->saw_manifest ? 2 : 0;
}

static int oc_gc_tombstone_actionable(int snaps, oc_u64 snaps_dev, const char *tname) {
    int tdir=oc_open_private(snaps,tname);
    if (tdir<0) return 0;
    char mf_buf[4096]; OcManifest mf; OcGcLeafCtx lctx;
    int state=oc_gc_inspect_tombstone(tdir,snaps_dev,tname+7,mf_buf,&mf,&lctx);
    if (oc_close(tdir)<0) state=0;
    return state>0;
}

static int oc_gc_candidate_owned(int snaps, oc_u64 snaps_dev, const char *cname) {
    char tname[72];
    if (!oc_join(tname,sizeof tname,".prune-",cname) || !oc_absent_at(snaps,tname)) return 0;
    int cdir=oc_open_private(snaps,cname);
    if (cdir<0) return 0;
    OcMeta cm; char mf_buf[4096]; OcManifest mf; OcGcLeafCtx cctx;
    int ok=oc_stat(cdir,&cm)>=0 && cm.device==snaps_dev &&
        oc_load_manifest(cdir,cname,mf_buf,sizeof mf_buf,&mf);
    for (unsigned j=0; ok&&j<mf.count; ++j)
        if (!oc_snap_leaf_allowed(mf.rows[j].name)) ok=0;
    if (ok) {
        cctx.dir_fd=cdir; cctx.snaps_dev=snaps_dev; cctx.mf=&mf; cctx.count=0; cctx.saw_manifest=0;
        ok=oc_dir_iter(cdir,oc_gc_leaf_cb,&cctx) && cctx.saw_manifest;
    }
    if (oc_close(cdir)<0) ok=0;
    return ok;
}

static int oc_gc_finish_tombstone(int snaps, oc_u64 snaps_dev, const char *tname) {
    int tdir=oc_open_private(snaps,tname);
    if (tdir<0) return 0;
    char mf_buf[4096]; OcManifest mf; OcGcLeafCtx lctx;
    int state=oc_gc_inspect_tombstone(tdir,snaps_dev,tname+7,mf_buf,&mf,&lctx);
    int ok=state>0;
    if (state==2) {
        for (unsigned i=0; ok&&i<lctx.count; ++i)
            if (oc_unlink(tdir,lctx.leaves[i])<0) ok=0;
        if (ok && oc_sync(tdir)<0) ok=0;
        oc_cut("gc_before_manifest_unlink");
        if (ok && oc_unlink(tdir,"files.sha256")<0) ok=0;
        oc_cut("gc_after_manifest_unlink");
    }
    if (oc_close(tdir)<0) ok=0;
    if (ok) ok=oc_rmdirat(snaps,tname)>=0 && oc_sync(snaps)>=0;
    return ok;
}

typedef struct {
    int snaps;
    oc_u64 snaps_dev;
    char pins[4][65];
    unsigned pin_count;
    char tombs[OC_GC_MAX][72];
    unsigned tomb_count;
    char cands[OC_GC_MAX][65];
    unsigned cand_count;
} OcGcScanCtx;

static int oc_gc_is_pinned(const OcGcScanCtx *s, const char *id) {
    for (unsigned i=0; i<s->pin_count; ++i) if (oc_equal(s->pins[i],id)) return 1;
    return 0;
}

static int oc_gc_scan_cb(const char *name, void *raw) {
    OcGcScanCtx *s=raw;
    if (oc_prefix(name,".prune-") && oc_hex(name+7,64)) {
        if (s->tomb_count<OC_GC_MAX && oc_gc_tombstone_actionable(s->snaps,s->snaps_dev,name) &&
            oc_join(s->tombs[s->tomb_count],sizeof s->tombs[0],"",name))
            ++s->tomb_count;
        return 1;
    }
    if (oc_hex(name,64) && !oc_gc_is_pinned(s,name)) {
        if (s->cand_count<OC_GC_MAX && oc_gc_candidate_owned(s->snaps,s->snaps_dev,name) &&
            oc_join(s->cands[s->cand_count],sizeof s->cands[0],"",name))
            ++s->cand_count;
    }
    return 1;
}

static int oc_gc_check_marker(int ram, int snaps, oc_u64 snaps_dev, long owner, long group, const char *marker, char out[65], int *present) {
    *present=0;
    if (oc_absent_at(ram,marker)) return 1;
    long fd=oc_openat(ram,marker,OC_READ,0);
    if (fd<0) return 0;
    OcMeta m;
    char buf[66];
    int n=-1;
    int ok=oc_stat((int)fd,&m)>=0 && (m.mode&OC_TYPE)==OC_REGULAR && m.size==65 &&
        m.uid==(unsigned)owner && m.gid==(unsigned)group;
    if (ok) n=oc_text_fd((int)fd,buf,sizeof buf);
    if (oc_close((int)fd)<0) ok=0;
    if (!ok || n!=65 || !oc_one_line(buf) || !oc_hex(buf,64)) return 0;
    int sdir=oc_open_private(snaps,buf);
    if (sdir<0) return 0;
    OcMeta sm;
    ok=oc_stat(sdir,&sm)>=0 && sm.device==snaps_dev;
    if (oc_close(sdir)<0) ok=0;
    if (!ok) return 0;
    for (unsigned i=0; i<65; ++i) out[i]=buf[i];
    *present=1;
    return 1;
}

int oc_gc_snapshots(const char *root_path, int lock_fd) {
    OcBoot *b=&oc_boot;
    b->root=b->data=b->ram=b->lock=b->snapshot=b->baseline=b->package=b->composed=b->stage=b->observer=b->log=-1;
    b->owner=oc_owner(); b->group=oc_group();
    OcMeta held;
    if (lock_fd>=0 && oc_stat(lock_fd,&held)<0) return 1;
    int snaps=-1, ok=1;
    b->root=(int)oc_openat(OC_CWD,root_path,OC_DIRECTORY,0);
    if (b->root<0) return 1;
    b->data=oc_open_private(b->root,OC_DATA);
    b->ram=oc_open_private(b->root,OC_RAM);
    if (b->data<0 || b->ram<0) { ok=0; goto out; }
    OcMeta expected_lock;
    if (oc_metadata(b->ram,"lock",&expected_lock)<0 ||
        expected_lock.mode!=(OC_REGULAR|0600) ||
        expected_lock.uid!=(unsigned)b->owner || expected_lock.gid!=(unsigned)b->group) { ok=0; goto out; }
    if (lock_fd>=0) {
        if (held.device!=expected_lock.device || held.inode!=expected_lock.inode ||
            held.mode!=expected_lock.mode || held.uid!=expected_lock.uid || held.gid!=expected_lock.gid) {
            ok=0; goto out;
        }
        long probe=oc_openat(b->ram,"lock",OC_READ,0);
        OcMeta pm;
        int ex=probe>=0 && oc_stat((int)probe,&pm)>=0 &&
            pm.device==expected_lock.device && pm.inode==expected_lock.inode &&
            oc_lock_held_ex((int)probe);
        if (probe>=0 && oc_close((int)probe)<0) ex=0;
        if (!ex) { ok=0; goto out; }
    } else {
        b->lock=(int)oc_openat(b->ram,"lock",OC_RW,0);
        OcMeta opened;
        if (b->lock<0 || oc_stat(b->lock,&opened)<0 || opened.device!=expected_lock.device ||
            opened.inode!=expected_lock.inode || oc_lock(b->lock)<0) { ok=0; goto out; }
    }
    if (!oc_mounts_mode(b->root,b->scratch,sizeof b->scratch,1)) { ok=0; goto out; }
    if (!oc_record_file(b,0,0) || !oc_equal(b->record_fields[8],"-")) { ok=0; goto out; }
    snaps=oc_open_private(b->data,"snapshots");
    OcMeta snaps_meta;
    if (snaps<0 || oc_stat(snaps,&snaps_meta)<0) { ok=0; goto out; }
    OcGcScanCtx scan;
    scan.snaps=snaps; scan.snaps_dev=snaps_meta.device;
    scan.pin_count=0; scan.tomb_count=0; scan.cand_count=0;
    for (unsigned i=4; i<=5; ++i) {
        int sdir=oc_open_private(snaps,b->record_fields[i]);
        OcMeta sm;
        int exist=sdir>=0 && oc_stat(sdir,&sm)>=0 && sm.device==snaps_meta.device;
        if (sdir>=0 && oc_close(sdir)<0) exist=0;
        if (!exist || !oc_join(scan.pins[scan.pin_count++],65,"",b->record_fields[i])) { ok=0; goto out; }
    }
    const char *markers[2]={"selected","access-selected"};
    for (unsigned i=0; i<2; ++i) {
        char id[65]; int present=0;
        if (!oc_gc_check_marker(b->ram,snaps,snaps_meta.device,b->owner,b->group,markers[i],id,&present)) {
            ok=0; goto out;
        }
        if (present && !oc_gc_is_pinned(&scan,id))
            (void)oc_join(scan.pins[scan.pin_count++],65,"",id);
    }
    if (!oc_dir_iter(snaps,oc_gc_scan_cb,&scan)) { ok=0; goto out; }
    unsigned done=0;
    for (unsigned i=0; i<scan.tomb_count && done<OC_GC_MAX; ++i) {
        if (oc_gc_finish_tombstone(snaps,snaps_meta.device,scan.tombs[i])) ++done;
        else ok=0;
    }
    for (unsigned i=0; i<scan.cand_count && done<OC_GC_MAX; ++i) {
        char tname[72];
        if (!oc_join(tname,sizeof tname,".prune-",scan.cands[i])) continue;
        if (!oc_absent_at(snaps,tname)) { ok=0; continue; }
        if (oc_rename(snaps,scan.cands[i],tname)<0 || oc_sync(snaps)<0) { ok=0; continue; }
        oc_cut("gc_tombstone_renamed");
        if (oc_gc_finish_tombstone(snaps,snaps_meta.device,tname)) ++done;
        else ok=0;
    }
out:
    if (snaps>=0 && oc_close(snaps)<0) ok=0;
    oc_close_boot(b);
    if (b->root>=0 && oc_close(b->root)<0) ok=0;
    return ok?0:1;
}
