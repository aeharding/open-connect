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
    char buf[OC_LINE_SIZE], meta[131];
    if (!oc_join4(buf,sizeof buf,key,"|",path,"|") || !oc_join(buf,sizeof buf,buf,digest)) return 0;
    if (absent) return oc_join(buf,sizeof buf,buf,"|-|-|-|-|-|-|-|-|-|-\n") && oc_write_all(fd,buf,oc_length(buf));
    (void)oc_meta_text(meta,m);
    return oc_join4(buf,sizeof buf,buf,meta,"\n",0) && oc_write_all(fd,buf,oc_length(buf));
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
        int w_on=oc_equal(new_flags[2],"1");
        const char *tpl[3]={w_on?"sm-normal-on.conf":"sm-normal-off.conf",
            w_on?"sm-wcp-on.conf":"sm-wcp-off.conf",
            w_on?"index-on.html":"index-off.html"};
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
        char hdr[160];
        plan_fd=oc_openat((int)work,"boot.plan",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        ok=plan_fd>=0 && oc_join4(hdr,sizeof hdr,"OCBP1|",b->record_fields[4],"|",b->record_fields[3]) &&
            oc_join(hdr,sizeof hdr,hdr,"\n") && oc_write_all((int)plan_fd,hdr,oc_length(hdr));
    }
    int reuse_touch = same_t2 && oc_equal(new_flags[1],"2") && b->touch_drift<=1;
    int reuse_base = same_b && same_svc && oc_equal(new_flags[6],"1");
    for (unsigned i=0; ok&&i<b->input_count; ++i) {
        OcInput *row=&b->inputs[i];
        if (oc_prefix(row->key,"current/")) continue;
        if (oc_prefix(row->key,"touch/devices/") && !reuse_touch) continue;
        if (oc_prefix(row->key,"base/") && !reuse_base) continue;
        ok=oc_emit_plan_row((int)plan_fd,row->key,row->path,row->digest,&row->meta,row->absent);
    }
    for (unsigned i=0; ok&&i<mcount; ++i) {
        char key[192], path[192];
        ok=oc_join(key,sizeof key,"current/",members[i]) &&
            oc_join(path,sizeof path,"@/",members[i]) &&
            oc_emit_plan_row((int)plan_fd,key,path,oc_pub.m_digest[i],&oc_pub.m_meta[i],0);
    }
    if (ok && oc_equal(new_flags[1],"2") && !reuse_touch) {
        for (unsigned i=0; ok&&i<2; ++i) {
            int pr=oc_emit_external_pin((int)plan_fd,b,oc_touch_pins[i].key,oc_touch_pins[i].path,
                                        oc_pin_digest(oc_touch_pins[i].key,oc_touch_pins[i].digest),1);
            if (pr) { err_rc=pr==1?92:1; ok=0; }
        }
    }
    if (ok) ok=oc_verified_text((int)work,"vui-plugins.list",oc_pub.m_digest[vui_idx],oc_pub.vui_list,sizeof oc_pub.vui_list);
    if (ok && oc_equal(new_flags[6],"1") && !reuse_base) {
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
    } else if (ok && !oc_equal(new_flags[6],"1") && oc_pub.vui_list[0]!=0) ok=0;
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
            ok=oc_join4(row,sizeof row,dig,"  ",nm,"\n");
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

/* Safe bounded unreachable snapshot, package, and composed-asset GC:
 * - Verifies inherited lock fd (no flock self-deadlock) or acquires lock standalone.
 * - Requires settled active OC1 with R_BEFORE=-, R_AFTER=-, legacy_undo=-.
 * - Snapshot GC pins R_BASE, R_CURRENT, and validated live selected/access-selected.
 * - Package & composed GC pins R_BACKEND, every surviving snapshot's package/selector,
 *   live runtime/usb-runtime sessions, and live feature/{uia.so,maintenance.js} symlinks.
 * - Fail-closed on any unreadable/unowned surviving snapshot or malformed RAM pointer.
 * - Resumes .prune-* tombstones first; unlinks non-manifest leaves before files.sha256.
 */
enum { OC_GC_SNAP=0, OC_GC_PKG=1, OC_GC_COMP=2, OC_GC_PINS_MAX=32 };

static int oc_gc_leaf_allowed(int kind, const char *name) {
    if (kind==OC_GC_SNAP) {
        static const char *const allowed[]={
            "autostart","config","dependencies","access","runlogin","sshd.conf",
            "selector","sm-normal.conf","sm-wcp.conf","index.html","mmui.xml",
            "vui-plugins.list","boot.plan"
        };
        for (unsigned i=0; i<sizeof allowed/sizeof *allowed; ++i)
            if (oc_equal(name,allowed[i])) return 1;
        return 0;
    }
    if (kind==OC_GC_COMP) {
        for (unsigned i=0; i<sizeof oc_composed_names/sizeof *oc_composed_names; ++i)
            if (oc_equal(name,oc_composed_names[i])) return 1;
        return 0;
    }
    return oc_key(name);
}

typedef struct {
    int dir_fd;
    oc_u64 store_dev;
    int kind;
    OcManifest *mf;
    char leaves[64][48];
    unsigned count;
    int saw_manifest;
} OcGcLeafCtx;

typedef struct {
    char mf_buf[8192];
    OcManifest mf;
    OcGcLeafCtx lctx;
} OcGcWork;
static OcGcWork oc_gc_work;

static int oc_gc_leaf_cb(const char *name, void *raw) {
    OcGcLeafCtx *c=raw;
    OcMeta m;
    if (oc_metadata(c->dir_fd,name,&m)<0 || (m.mode&OC_TYPE)!=OC_REGULAR || m.device!=c->store_dev) return -1;
    if (oc_equal(name,"files.sha256")) { c->saw_manifest=1; return 1; }
    if (!c->mf || !oc_digest(c->mf,name) || !oc_gc_leaf_allowed(c->kind,name)) return -1;
    if (c->count>=64 || !oc_join(c->leaves[c->count],sizeof c->leaves[0],"",name)) return -1;
    ++c->count;
    return 1;
}

static int oc_gc_empty_cb(const char *name, void *raw) {
    (void)name; *(int *)raw=1; return 0;
}

static int oc_gc_load_manifest(int dir, oc_u64 store_dev, const char *id, int kind, long owner, long group, char *buf, unsigned cap, OcManifest *mf) {
    if (kind!=OC_GC_COMP) {
        if (!oc_verified_text(dir,"files.sha256",id,buf,cap) || !oc_manifest(buf,mf,0)) return 0;
        if (kind==OC_GC_PKG && (mf->count>64 || !oc_digest(mf,"VERSION") || !oc_digest(mf,"INSTANCE"))) return 0;
    } else {
        long fd=oc_openat(dir,"files.sha256",OC_READ,0);
        if (fd<0) return 0;
        OcMeta before, after;
        int n=-1;
        if (oc_stat((int)fd,&before)>=0 && before.mode==(OC_REGULAR|0600) &&
            before.device==store_dev && before.uid==(unsigned)owner &&
            before.gid==(unsigned)group && before.size<cap)
            n=oc_text_fd((int)fd,buf,cap);
        int ok=n>=0 && (oc_u64)n==before.size && oc_stat((int)fd,&after)>=0 && oc_meta_equal(&before,&after);
        if (oc_close((int)fd)<0) ok=0;
        if (!ok || !oc_manifest(buf,mf,0) || !mf->count) return 0;
    }
    for (unsigned i=0; i<mf->count; ++i)
        if (!oc_gc_leaf_allowed(kind,mf->rows[i].name)) return 0;
    return 1;
}

/* Returns 0=not actionable, 1=empty (manifest absent), 2=manifest+leaves valid in oc_gc_work.lctx. */
static int oc_gc_inspect_tombstone(int tdir, oc_u64 store_dev, const char *id, int kind, long owner, long group) {
    OcMeta tm;
    if (oc_stat(tdir,&tm)<0 || tm.device!=store_dev) return 0;
    if (oc_absent_at(tdir,"files.sha256")) {
        int nonempty=0;
        return oc_dir_iter(tdir,oc_gc_empty_cb,&nonempty) && !nonempty ? 1 : 0;
    }
    if (!oc_gc_load_manifest(tdir,store_dev,id,kind,owner,group,oc_gc_work.mf_buf,sizeof oc_gc_work.mf_buf,&oc_gc_work.mf)) return 0;
    oc_gc_work.lctx.dir_fd=tdir; oc_gc_work.lctx.store_dev=store_dev; oc_gc_work.lctx.kind=kind;
    oc_gc_work.lctx.mf=&oc_gc_work.mf; oc_gc_work.lctx.count=0; oc_gc_work.lctx.saw_manifest=0;
    return oc_dir_iter(tdir,oc_gc_leaf_cb,&oc_gc_work.lctx) && oc_gc_work.lctx.saw_manifest ? 2 : 0;
}

static int oc_gc_tombstone_actionable(int store, oc_u64 store_dev, const char *tname, int kind, long owner, long group) {
    int tdir=oc_open_private(store,tname);
    if (tdir<0) return 0;
    int state=oc_gc_inspect_tombstone(tdir,store_dev,tname+7,kind,owner,group);
    if (oc_close(tdir)<0) state=0;
    return state>0;
}

static int oc_gc_candidate_owned(int store, oc_u64 store_dev, const char *cname, int kind, long owner, long group) {
    char tname[72];
    if (!oc_join(tname,sizeof tname,".prune-",cname) || !oc_absent_at(store,tname)) return 0;
    int cdir=oc_open_private(store,cname);
    if (cdir<0) return 0;
    OcMeta cm;
    int ok=oc_stat(cdir,&cm)>=0 && cm.device==store_dev &&
        oc_gc_load_manifest(cdir,store_dev,cname,kind,owner,group,oc_gc_work.mf_buf,sizeof oc_gc_work.mf_buf,&oc_gc_work.mf);
    if (ok) {
        oc_gc_work.lctx.dir_fd=cdir; oc_gc_work.lctx.store_dev=store_dev; oc_gc_work.lctx.kind=kind;
        oc_gc_work.lctx.mf=&oc_gc_work.mf; oc_gc_work.lctx.count=0; oc_gc_work.lctx.saw_manifest=0;
        ok=oc_dir_iter(cdir,oc_gc_leaf_cb,&oc_gc_work.lctx) &&
            oc_gc_work.lctx.saw_manifest && oc_gc_work.lctx.count==oc_gc_work.mf.count;
    }
    if (ok && kind==OC_GC_COMP) {
        for (unsigned i=0; ok && i<oc_gc_work.lctx.count; ++i) {
            const char *leaf=oc_gc_work.lctx.leaves[i];
            const char *exp=oc_digest(&oc_gc_work.mf,leaf);
            long fd=oc_openat(cdir,leaf,OC_READ,0);
            char got[65]; OcMeta lm;
            ok=fd>=0 && exp &&
                oc_hash_copy((int)fd,-1,33554432,got,&lm)==OC_COPY_OK &&
                lm.mode==(OC_REGULAR|0600) && lm.device==store_dev &&
                lm.uid==(unsigned)owner && lm.gid==(unsigned)group &&
                oc_equal(got,exp);
            if (fd>=0 && oc_close((int)fd)<0) ok=0;
        }
    }
    if (oc_close(cdir)<0) ok=0;
    return ok;
}

static int oc_gc_finish_tombstone(int store, oc_u64 store_dev, const char *tname, int kind, long owner, long group) {
    int tdir=oc_open_private(store,tname);
    if (tdir<0) return 0;
    int state=oc_gc_inspect_tombstone(tdir,store_dev,tname+7,kind,owner,group);
    int ok=state>0;
    if (state==2) {
        for (unsigned i=0; ok&&i<oc_gc_work.lctx.count; ++i)
            if (oc_unlink(tdir,oc_gc_work.lctx.leaves[i])<0) ok=0;
        if (ok && oc_sync(tdir)<0) ok=0;
        oc_cut("gc_before_manifest_unlink");
        if (ok && oc_unlink(tdir,"files.sha256")<0) ok=0;
        oc_cut("gc_after_manifest_unlink");
    }
    if (oc_close(tdir)<0) ok=0;
    if (ok) ok=oc_rmdirat(store,tname)>=0 && oc_sync(store)>=0;
    return ok;
}

typedef struct {
    int store;
    oc_u64 store_dev;
    int kind;
    long owner, group;
    char pins[OC_GC_PINS_MAX][65];
    unsigned pin_count;
    char tombs[OC_GC_MAX][72];
    unsigned tomb_count;
    char cands[OC_GC_MAX][65];
    unsigned cand_count;
} OcGcScanCtx;
static OcGcScanCtx oc_gc_scan;

static int oc_gc_is_pinned(const OcGcScanCtx *s, const char *id) {
    for (unsigned i=0; i<s->pin_count; ++i) if (oc_equal(s->pins[i],id)) return 1;
    return 0;
}

static int oc_gc_add_pin(OcGcScanCtx *s, const char *id) {
    if (!oc_hex(id,64)) return 0;
    if (oc_gc_is_pinned(s,id)) return 1;
    if (s->pin_count>=OC_GC_PINS_MAX) return 0;
    return oc_join(s->pins[s->pin_count++],65,"",id);
}

static int oc_gc_scan_cb(const char *name, void *raw) {
    OcGcScanCtx *s=raw;
    if (oc_prefix(name,".prune-") && oc_hex(name+7,64)) {
        if (s->tomb_count<OC_GC_MAX &&
            oc_gc_tombstone_actionable(s->store,s->store_dev,name,s->kind,s->owner,s->group) &&
            oc_join(s->tombs[s->tomb_count],sizeof s->tombs[0],"",name))
            ++s->tomb_count;
        return 1;
    }
    if (oc_hex(name,64) && !oc_gc_is_pinned(s,name)) {
        if (s->cand_count<OC_GC_MAX &&
            oc_gc_candidate_owned(s->store,s->store_dev,name,s->kind,s->owner,s->group) &&
            oc_join(s->cands[s->cand_count],sizeof s->cands[0],"",name))
            ++s->cand_count;
    }
    return 1;
}

static int oc_gc_run_store(int store, oc_u64 store_dev, int kind, long owner, long group) {
    oc_gc_scan.store=store; oc_gc_scan.store_dev=store_dev; oc_gc_scan.kind=kind;
    oc_gc_scan.owner=owner; oc_gc_scan.group=group;
    oc_gc_scan.tomb_count=0; oc_gc_scan.cand_count=0;
    if (!oc_dir_iter(store,oc_gc_scan_cb,&oc_gc_scan)) return 0;
    int ok=1; unsigned done=0;
    for (unsigned i=0; i<oc_gc_scan.tomb_count && done<OC_GC_MAX; ++i) {
        if (oc_gc_finish_tombstone(store,store_dev,oc_gc_scan.tombs[i],kind,owner,group)) ++done;
        else ok=0;
    }
    for (unsigned i=0; i<oc_gc_scan.cand_count && done<OC_GC_MAX; ++i) {
        char tname[72];
        if (!oc_join(tname,sizeof tname,".prune-",oc_gc_scan.cands[i])) continue;
        if (!oc_absent_at(store,tname)) { ok=0; continue; }
        if (oc_rename(store,oc_gc_scan.cands[i],tname)<0 || oc_sync(store)<0) { ok=0; continue; }
        oc_cut("gc_tombstone_renamed");
        if (oc_gc_finish_tombstone(store,store_dev,tname,kind,owner,group)) ++done;
        else ok=0;
    }
    return ok;
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

static int oc_gc_config_pkg(char *text, char out[65], int *has_pkg) {
    *has_pkg=0;
    if (oc_prefix(text,"OC2\n")) {
        unsigned hits=0;
        char *p=text+4;
        while (*p) {
            char *line=p;
            while (*p && *p!='\n') ++p;
            if (!*p) return 0;
            *p++=0;
            if (oc_prefix(line,"package=")) {
                const char *val=line+8;
                if (++hits!=1) return 0;
                if (oc_equal(val,"-")) *has_pkg=0;
                else if (oc_hex(val,64)) { if (!oc_join(out,65,"",val)) return 0; *has_pkg=1; }
                else return 0;
            }
        }
        return hits==1;
    }
    char *f[5];
    if (!oc_one_line(text) || oc_fields(text,f,5)!=5) return 0;
    if (oc_equal(f[0],"-")) return 1;
    if (!oc_hex(f[0],64) || !oc_join(out,65,"",f[0])) return 0;
    *has_pkg=1;
    return 1;
}

typedef struct {
    int snaps;
    oc_u64 snaps_dev;
    long owner, group;
    int unsafe;
} OcGcSnapPinCtx;

static int oc_gc_snap_pkg_cb(const char *name, void *raw) {
    OcGcSnapPinCtx *c=raw;
    if (oc_prefix(name,".prune-") && oc_hex(name+7,64)) return 1;
    if (!oc_hex(name,64)) return 1;
    int sdir=oc_open_private(c->snaps,name);
    if (sdir<0) { c->unsafe=1; return 0; }
    OcMeta sm; char cfg[1024], sel[256], pkg[65]; int has_pkg=0;
    int ok=oc_stat(sdir,&sm)>=0 && sm.device==c->snaps_dev &&
        oc_gc_load_manifest(sdir,c->snaps_dev,name,OC_GC_SNAP,c->owner,c->group,oc_gc_work.mf_buf,sizeof oc_gc_work.mf_buf,&oc_gc_work.mf) &&
        oc_saved_text(sdir,&oc_gc_work.mf,"config",cfg,sizeof cfg) &&
        oc_gc_config_pkg(cfg,pkg,&has_pkg) &&
        (!has_pkg || oc_gc_add_pin(&oc_gc_scan,pkg));
    if (ok && oc_digest(&oc_gc_work.mf,"selector")) {
        char *sf[3];
        ok=oc_saved_text(sdir,&oc_gc_work.mf,"selector",sel,sizeof sel);
        if (ok && !oc_equal(sel,"-\n"))
            ok=oc_fields_line(sel,sf,3) && oc_gc_add_pin(&oc_gc_scan,sf[2]);
    }
    if (oc_close(sdir)<0) ok=0;
    if (!ok) { c->unsafe=1; return 0; }
    return 1;
}

static int oc_gc_pin_session(int ram, oc_u64 ram_dev, const char *root_path, long owner, long group, const char *link_name) {
    if (oc_absent_at(ram,link_name)) return 1;
    OcMeta lm;
    if (oc_metadata(ram,link_name,&lm)<0 || (lm.mode&OC_TYPE)!=0120000 ||
        lm.uid!=(unsigned)owner || lm.gid!=(unsigned)group || lm.size==0 || lm.size>=512) return 0;
    char target[512], abs_prefix[512];
    long n=oc_readlink(ram,link_name,target,sizeof target-1);
    if (n<=0 || (oc_u64)n!=lm.size) return 0;
    target[n]=0;
    if (!oc_join(abs_prefix,sizeof abs_prefix,oc_equal(root_path,"/")?"":root_path,"/" OC_RAM "/sessions/session-")) return 0;
    const char *leaf=0;
    if (oc_prefix(target,"sessions/session-")) leaf=target+9;
    else if (oc_prefix(target,abs_prefix)) leaf=target+oc_length(abs_prefix)-8;
    else return 0;
    for (const char *p=leaf; *p; ++p) if (*p=='/') return 0;
    if (!oc_key(leaf)) return 0;
    int sess=oc_open_private(ram,"sessions");
    if (sess<0) return 0;
    OcMeta sm, sdm;
    int sdir=-1;
    int ok=oc_stat(sess,&sm)>=0 && sm.device==ram_dev;
    if (ok) {
        sdir=oc_open_private(sess,leaf);
        ok=sdir>=0 && oc_stat(sdir,&sdm)>=0 && sdm.device==ram_dev;
    }
    if (oc_close(sess)<0) ok=0;
    if (!ok) { if (sdir>=0) (void)oc_close(sdir); return 0; }
    long mfd=oc_openat(sdir,"files.sha256",OC_READ,0);
    char digest[65]; OcMeta mm;
    ok=mfd>=0 && oc_hash_copy((int)mfd,-1,65536,digest,&mm)==OC_COPY_OK &&
        mm.device==ram_dev && mm.uid==(unsigned)owner && mm.gid==(unsigned)group &&
        oc_gc_add_pin(&oc_gc_scan,digest);
    if (mfd>=0 && oc_close((int)mfd)<0) ok=0;
    if (oc_close(sdir)<0) ok=0;
    return ok;
}

static int oc_gc_pin_feature_link(int fdir, long owner, long group, const char *name, const char *prefix, const char *suffix) {
    if (oc_absent_at(fdir,name)) return 1;
    OcMeta m;
    if (oc_metadata(fdir,name,&m)<0) return 0;
    if ((m.mode&OC_TYPE)==OC_REGULAR) return 1;
    if ((m.mode&OC_TYPE)!=0120000 || m.uid!=(unsigned)owner || m.gid!=(unsigned)group ||
        m.size==0 || m.size>=256) return 0;
    char target[256];
    long n=oc_readlink(fdir,name,target,sizeof target-1);
    if (n<=0 || (oc_u64)n!=m.size) return 0;
    target[n]=0;
    unsigned plen=oc_length(prefix), slen=oc_length(suffix);
    if ((unsigned)n!=plen+64+slen || !oc_prefix(target,prefix) || !oc_equal(target+plen+64,suffix)) return 0;
    char id[65];
    for (unsigned i=0; i<64; ++i) id[i]=target[plen+i];
    id[64]=0;
    return oc_gc_add_pin(&oc_gc_scan,id);
}

int oc_gc_snapshots(const char *root_path, int lock_fd) {
    OcBoot *b=&oc_boot;
    b->root=b->data=b->ram=b->lock=b->snapshot=b->baseline=b->package=b->composed=b->stage=b->observer=b->log=-1;
    b->owner=oc_owner(); b->group=oc_group();
    OcMeta held;
    if (lock_fd>=0 && oc_stat(lock_fd,&held)<0) return 1;
    int snaps=-1, pkgs=-1, comp=-1, ok=1;
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
    oc_gc_scan.pin_count=0;
    for (unsigned i=4; i<=5; ++i) {
        int sdir=oc_open_private(snaps,b->record_fields[i]);
        OcMeta sm;
        int exist=sdir>=0 && oc_stat(sdir,&sm)>=0 && sm.device==snaps_meta.device;
        if (sdir>=0 && oc_close(sdir)<0) exist=0;
        if (!exist || !oc_gc_add_pin(&oc_gc_scan,b->record_fields[i])) { ok=0; goto out; }
    }
    const char *markers[2]={"selected","access-selected"};
    for (unsigned i=0; i<2; ++i) {
        char id[65]; int present=0;
        if (!oc_gc_check_marker(b->ram,snaps,snaps_meta.device,b->owner,b->group,markers[i],id,&present)) {
            ok=0; goto out;
        }
        if (present && !oc_gc_add_pin(&oc_gc_scan,id)) { ok=0; goto out; }
    }
    if (!oc_gc_run_store(snaps,snaps_meta.device,OC_GC_SNAP,b->owner,b->group)) { ok=0; goto out; }

    /* Cross-generation package & composed GC: collect all pins fail-closed.
     * Any unrecognized surviving snapshot or RAM pointer conservatively skips
     * package/composed pruning without deleting anything or failing snapshot GC.
     */
    oc_gc_scan.pin_count=0;
    OcMeta ram_meta;
    int pkg_safe=oc_stat(b->ram,&ram_meta)>=0 &&
        oc_gc_add_pin(&oc_gc_scan,b->record_fields[3]) &&
        oc_gc_pin_session(b->ram,ram_meta.device,root_path,b->owner,b->group,"runtime") &&
        oc_gc_pin_session(b->ram,ram_meta.device,root_path,b->owner,b->group,"usb-runtime");
    if (pkg_safe && !oc_absent_at(b->ram,"feature")) {
        int fdir=oc_open_private(b->ram,"feature");
        pkg_safe=fdir>=0 &&
            oc_gc_pin_feature_link(fdir,b->owner,b->group,"uia.so",
                "../../mnt/data_persist/open-connect/composed/","/uia.so") &&
            oc_gc_pin_feature_link(fdir,b->owner,b->group,"maintenance.js",
                "../../mnt/data_persist/open-connect/packages/","/maintenance.js");
        if (fdir>=0 && oc_close(fdir)<0) pkg_safe=0;
    }
    OcGcSnapPinCtx sp={snaps,snaps_meta.device,b->owner,b->group,0};
    if (!pkg_safe || !oc_dir_iter(snaps,oc_gc_snap_pkg_cb,&sp) || sp.unsafe) goto out;
    if (!oc_absent_at(b->data,"packages")) {
        pkgs=oc_open_private(b->data,"packages");
        OcMeta pm;
        if (pkgs<0 || oc_stat(pkgs,&pm)<0 || pm.device!=snaps_meta.device ||
            !oc_gc_run_store(pkgs,pm.device,OC_GC_PKG,b->owner,b->group)) ok=0;
    }
    if (!oc_absent_at(b->data,"composed")) {
        comp=oc_open_private(b->data,"composed");
        OcMeta cm;
        if (comp<0 || oc_stat(comp,&cm)<0 || cm.device!=snaps_meta.device ||
            !oc_gc_run_store(comp,cm.device,OC_GC_COMP,b->owner,b->group)) ok=0;
    }
out:
    if (comp>=0 && oc_close(comp)<0) ok=0;
    if (pkgs>=0 && oc_close(pkgs)<0) ok=0;
    if (snaps>=0 && oc_close(snaps)<0) ok=0;
    oc_close_boot(b);
    if (b->root>=0 && oc_close(b->root)<0) ok=0;
    return ok?0:1;
}
