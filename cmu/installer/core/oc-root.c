/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native physical-root publisher, RelFS remount, NVRAM CAS commit, and
 * boot-selector / staging verification & retirement.
 */
#include "oc-core.h"
#ifdef OC_HOST
#include <stdlib.h>
#endif

static int oc_split_parent_leaf(const char *rel, char parent[192], const char **leaf_out) {
    unsigned n=oc_length(rel), slash=0;
    for (unsigned i=0; i<n; ++i) if (rel[i]=='/') slash=i;
    if (!slash || slash>=192 || slash+1>=n) return 0;
    for (unsigned i=0; i<slash; ++i) parent[i]=rel[i];
    parent[slash]=0;
    *leaf_out=rel+slash+1;
    return 1;
}

static int oc_hash_prefix_at(int dir, const char *name, oc_u64 limit, char digest[65]) {
    long fd=oc_openat(dir,name,OC_READ,0);
    if (fd<0) return 0;
    OcMeta m={0};
    int ok=oc_stat((int)fd,&m)>=0 && (m.mode&OC_TYPE)==OC_REGULAR && limit<=m.size;
    OcHash h; oc_hash_init(&h);
    oc_u8 buf[4096]; oc_u64 rem=limit;
    while (ok && rem) {
        unsigned want=rem>sizeof buf?(unsigned)sizeof buf:(unsigned)rem;
        long r=oc_read((int)fd,buf,want);
        if (r==-4) continue;
        if (r<=0) { ok=0; break; }
        oc_hash_add(&h,buf,(unsigned)r);
        rem-=(oc_u64)r;
    }
    if (oc_close((int)fd)<0) ok=0;
    if (ok) oc_hash_finish(&h,digest);
    return ok;
}

static int oc_root_is_mode(int root, int rw) {
    return oc_mounts_mode(root,oc_mscratch,sizeof oc_mscratch,rw?2:0);
}

int oc_remount(int root, const char *root_path, int rw) {
    (void)root_path;
#ifdef OC_HOST
    if (getenv("OC_HOST_REMOUNT_FAIL")) return 0;
    const char *mpaths[2]={"proc/self/mounts","proc/mounts"};
    int updated=0;
    for (unsigned mi=0; mi<2; ++mi) {
        char *buf=oc_big_buf, *out=oc_big_buf+16384;
        int n=oc_text(root,mpaths[mi],buf,16384,0);
        if (n<=0) continue;
        const char *from=rw?"ro,noatime":"rw,noatime";
        const char *to=rw?"rw,noatime":"ro,noatime";
        unsigned used=0; char *p=buf;
        while (*p) {
            char *line=p;
            while (*p && *p!='\n') ++p;
            int has_nl=(*p=='\n');
            if (has_nl) *p++=0;
            if (oc_prefix(line,"/dev/ffx01p1 / relfs ")) {
                const char *q=line;
                while (*q) {
                    if (oc_prefix(q,from)) {
                        unsigned tl=oc_length(to);
                        if (used+tl>=16384) return 0;
                        for (unsigned j=0; j<tl; ++j) out[used++]=to[j];
                        q+=oc_length(from);
                    } else {
                        if (used+1>=16384) return 0;
                        out[used++]=*q++;
                    }
                }
            } else {
                unsigned ll=oc_length(line);
                if (used+ll>=16384) return 0;
                for (unsigned j=0; j<ll; ++j) out[used++]=line[j];
            }
            if (has_nl) { if (used+1>=16384) return 0; out[used++]='\n'; }
        }
        out[used]=0;
        long fd=oc_beneath(root,mpaths[mi],OC_WRITE|OC_TRUNC,0600);
        if (fd>=0) {
            int ok=oc_write_all((int)fd,out,used);
            if (oc_close((int)fd)<0) ok=0;
            if (ok && mi==0) updated=1;
        }
    }
    return updated && oc_root_is_mode(root,rw);
#else
    char *argv[]={
        "/bin/busybox","timeout","-t","8","-s","TERM",
        "/bin/busybox","mount","-i","-n","-t","relfs","-o",
        rw?"remount,rw,noatime":"remount,ro,noatime","/dev/ffx01p1","/",0
    };
    if (oc_run_cmd("/bin/busybox",argv,-1,0,0,-1)!=0) return 0;
    return oc_root_is_mode(root,rw);
#endif
}

static int oc_write_sysfs_at(int dir, const char *path, const char *text) {
    long fd=oc_openat(dir,path,OC_WRITE|OC_TRUNC,0);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,text,oc_length(text));
    if (oc_close((int)fd)<0) ok=0;
    return ok;
}

int oc_nvram_change(int root, const char *expected, const char *desired) {
    if (!oc_nvram_value(expected) || !oc_nvram_value(desired)) return 0;
#ifdef OC_HOST
    int skip_fw=getenv("OC_HOST_SKIP_FW_GUARD")!=0;
    const char *nv_fail=getenv("OC_HOST_NVRAM_FAIL");
#else
    int skip_fw=0;
#endif
    if (!skip_fw) {
        if (!oc_version_ok(root,oc_big_buf,sizeof oc_big_buf)) return 0;
        long lfd=oc_beneath(root,"jci/lvds/lvds_service",OC_READ,0);
        char dig[65]; OcMeta lm={0};
        int lok=lfd>=0 && oc_hash_copy((int)lfd,-1,33554432,dig,&lm)==OC_COPY_OK &&
            oc_equal(dig,oc_pin_digest("root/lvds-service",
                "19a56b9e7b9f7399b152dbc7e8bd8de3fa01f154e45e8981becec6e96d3f70eb"));
        if (lfd>=0 && oc_close((int)lfd)<0) lok=0;
        if (!lok) return 0;
    }
    long tmp=oc_beneath(root,"tmp",OC_DIRECTORY,0);
    if (tmp<0) return 0;
    long lfd=oc_openat((int)tmp,"oc-lvds-setting.lock",OC_RW|OC_CREATE,0600);
    (void)oc_close((int)tmp);
    OcMeta lm={0};
    long owner=oc_owner(), group=oc_group();
    if (lfd<0 || oc_stat((int)lfd,&lm)<0 || (lm.mode&OC_TYPE)!=OC_REGULAR ||
        (lm.mode&0077) || lm.uid!=(unsigned)owner || lm.gid!=(unsigned)group ||
        oc_lock((int)lfd)<0) {
        if (lfd>=0) (void)oc_close((int)lfd);
        return 0;
    }
    int ok=0;
    char cur[16], chk[16];
    /* Note: /sys/class/nvram/nv-config is a sysfs symlink on Linux 3.0.35; open
     * its attributes via paths beneath root so O_NOFOLLOW checks the leaf. */
    if (oc_nvram_at(root,cur) && oc_equal(cur,expected)) {
        ok=1;
#ifdef OC_HOST
        if (nv_fail && oc_equal(nv_fail,"before")) ok=0;
#endif
        if (ok && !oc_equal(desired,expected)) {
            if (oc_equal(desired,"absent")) {
                ok=oc_write_sysfs_at(root,"sys/class/nvram/nv-config/remove","lvds_speed_restriction\n");
#ifdef OC_HOST
                if (ok) {
                    long kdir=oc_openat(root,"sys/class/nvram/nv-config/keys",OC_DIRECTORY,0);
                    if (kdir>=0) {
                        if (!oc_absent_at((int)kdir,"lvds_speed_restriction"))
                            (void)oc_unlink((int)kdir,"lvds_speed_restriction");
                        (void)oc_close((int)kdir);
                    }
                }
#endif
            } else if (oc_equal(expected,"absent")) {
                char line[48];
                ok=oc_join4(line,sizeof line,"lvds_speed_restriction=",desired,"\n",0) &&
                    oc_write_sysfs_at(root,"sys/class/nvram/nv-config/add",line);
#ifdef OC_HOST
                if (ok) {
                    long kdir=oc_openat(root,"sys/class/nvram/nv-config/keys",OC_DIRECTORY,0);
                    if (kdir>=0) {
                        if (oc_absent_at((int)kdir,"lvds_speed_restriction")) {
                            char val[20];
                            if (oc_join(val,sizeof val,desired,"\n"))
                                (void)oc_new_text((int)kdir,"lvds_speed_restriction",val,0600);
                        }
                        (void)oc_close((int)kdir);
                    }
                }
#endif
            } else {
                char val[20];
                ok=oc_join(val,sizeof val,desired,"\n") &&
                    oc_write_sysfs_at(root,"sys/class/nvram/nv-config/keys/lvds_speed_restriction",val);
            }
            if (ok) ok=oc_nvram_at(root,chk) && oc_equal(chk,desired);
        }
#ifdef OC_HOST
        if (ok && nv_fail && oc_equal(nv_fail,"after")) ok=0;
#endif
        if (ok) ok=oc_write_sysfs_at(root,"sys/class/nvram/nv-config/commit","\n") &&
            oc_nvram_at(root,chk) && oc_equal(chk,desired);
    }
    if (oc_close((int)lfd)<0) ok=0;
    return ok;
}

static int oc_target_matches_spec(int parent, const char *leaf, const char *exp_hash, const char *exp_mode) {
    if (oc_equal(exp_hash,"-")) return oc_absent_at(parent,leaf);
    char got[65], ms[40]; OcMeta m={0};
    return oc_hash_file_at(parent,leaf,got,&m) && oc_equal(got,exp_hash) &&
        oc_meta_mode_str(&m,ms) && oc_equal(ms,exp_mode);
}

static int oc_stage_matches_src(int parent, const char *work_leaf, int src_dir, const char *src_leaf) {
    char wdig[65], pdig[65]; OcMeta wm={0};
    if (!oc_hash_file_at(parent,work_leaf,wdig,&wm)) return 0;
    return oc_hash_prefix_at(src_dir,src_leaf,wm.size,pdig) && oc_equal(wdig,pdig);
}

int oc_root_publish(int root, const char *root_path, int data_fd, const char *rev,
                    const char *target_rel, const char *src_rel, const char *mode_str,
                    const char *expected_hash, const char *expected_mode,
                    const char *hold_rel, const char *hold_mode, int retire,
                    const char *base_snap, long owner, long group) {
    if (!oc_hex(rev,32)) return 0;
    int is_auto=oc_equal(target_rel,"usr/bin/autostart");
    int is_login=oc_equal(target_rel,"usr/bin/runlogin");
    int is_sshd=oc_equal(target_rel,"etc/ssh/sshd_config");
    int is_sel=oc_equal(target_rel,"usr/bin/open-connect-boot-select");
    if (!is_auto && !is_login && !is_sshd && !is_sel) return 0;
    int h_keep=hold_mode && oc_equal(hold_mode,"keep");
    int h_restore=hold_mode && oc_equal(hold_mode,"restore");
    const char *held_leaf=0; oc_u64 held_ino=0;
    if (!hold_mode || !*hold_mode) {
        if (hold_rel && *hold_rel) return 0;
    } else if (h_keep || h_restore) {
        if (!is_login || !hold_rel || !oc_prefix(hold_rel,"usr/bin/.open-connect-runlogin-")) return 0;
        held_leaf=hold_rel+8;
        if (!oc_decimal(hold_rel+31,&held_ino)) return 0;
    } else return 0;

    int is_remove=oc_equal(src_rel,"-");
    if (is_remove) {
        if (!is_sel || !oc_equal(mode_str,"-") || h_keep || h_restore || retire) return 0;
    }
    if (oc_equal(expected_hash,"-")) {
        if (!is_sel || !oc_equal(expected_mode,"-")) return 0;
    } else {
        unsigned dm, du, dg;
        if (!oc_hex(expected_hash,64) || !oc_metadata_mode(expected_mode,&dm,&du,&dg)) return 0;
    }

    char parent_rel[192], work_leaf[96]; const char *leaf=0;
    if (!oc_split_parent_leaf(target_rel,parent_rel,&leaf)) return 0;
    if (is_auto) { if (!oc_join(work_leaf,sizeof work_leaf,".open-connect-",rev)) return 0; }
    else { if (!oc_join4(work_leaf,sizeof work_leaf,".open-connect-",rev,"-",leaf)) return 0; }

    if (!oc_mounts_mode(root,oc_mscratch,sizeof oc_mscratch,1)) return 0;

    long parent=oc_beneath(root,parent_rel,OC_DIRECTORY,0);
    if (parent<0) return 0;
    long src_dir=-1; const char *src_leaf=0;
    int ok=1, has_id=0; oc_u64 stage_dev=0, stage_ino=0;

    if (!is_remove) {
        char sp[192];
        if (!oc_split_parent_leaf(src_rel,sp,&src_leaf)) { ok=0; goto done; }
        src_dir=oc_beneath(data_fd,sp,OC_DIRECTORY,0);
        if (src_dir<0) { ok=0; goto done; }
    }
    if (!oc_target_matches_spec((int)parent,leaf,expected_hash,expected_mode)) { ok=0; goto done; }
    if (is_remove) {
        if (!oc_absent_at((int)parent,work_leaf)) { ok=0; goto done; }
        if (!oc_equal(expected_hash,"-")) {
            if (!oc_remount(root,root_path,1) ||
                !oc_target_matches_spec((int)parent,leaf,expected_hash,expected_mode) ||
                oc_unlink((int)parent,leaf)<0) { ok=0; goto done; }
            oc_cut("root_publish_unlinked");
        }
        if (oc_sync((int)parent)<0) ok=0;
        goto done;
    }
    if (!oc_absent_at((int)parent,work_leaf)) {
        if (!oc_stage_matches_src((int)parent,work_leaf,(int)src_dir,src_leaf)) { ok=0; goto done; }
        OcMeta wm={0};
        if (oc_metadata((int)parent,work_leaf,&wm)<0) { ok=0; goto done; }
        if (h_restore) {
            OcMeta hm={0};
            if (oc_metadata((int)parent,held_leaf,&hm)<0 || wm.device!=hm.device || wm.inode!=hm.inode) {
                ok=0; goto done;
            }
        }
        has_id=1; stage_dev=wm.device; stage_ino=wm.inode;
    }
    if (retire) {
        if (oc_sync((int)parent)<0) ok=0;
        goto done;
    }

    char src_hash[65]; OcMeta sm={0};
    if (!oc_hash_file_at((int)src_dir,src_leaf,src_hash,&sm)) { ok=0; goto done; }
    if (!oc_equal(expected_hash,src_hash) || !oc_equal(expected_mode,mode_str)) {
        unsigned pm, pu, pg;
        if (!oc_metadata_mode(mode_str,&pm,&pu,&pg)) { ok=0; goto done; }
        if (!oc_remount(root,root_path,1)) { ok=0; goto done; }
        if (h_keep) {
            if (oc_absent_at((int)parent,held_leaf)) {
                OcMeta tm={0};
                if (oc_metadata((int)parent,leaf,&tm)<0 || tm.inode!=held_ino ||
                    oc_link((int)parent,leaf,(int)parent,held_leaf)<0) { ok=0; goto done; }
            }
            if (!oc_access_hold_verify(root,data_fd,base_snap,owner,group)) { ok=0; goto done; }
            long hfd=oc_openat((int)parent,held_leaf,OC_READ,0);
            int hok=hfd>=0 && oc_sync((int)hfd)>=0;
            if (hfd>=0 && oc_close((int)hfd)<0) hok=0;
            if (!hok || oc_sync((int)parent)<0) { ok=0; goto done; }
        }
        if (oc_absent_at((int)parent,work_leaf)) {
            if (h_restore) {
                OcMeta hm={0}; char hms[40];
                if (!oc_access_hold_verify(root,data_fd,base_snap,owner,group) ||
                    oc_metadata((int)parent,held_leaf,&hm)<0 ||
                    !oc_meta_mode_str(&hm,hms) || !oc_equal(hms,mode_str) ||
                    oc_link((int)parent,held_leaf,(int)parent,work_leaf)<0) { ok=0; goto done; }
            } else {
                long cfd=oc_openat((int)parent,work_leaf,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
                if (cfd<0 || oc_close((int)cfd)<0) { ok=0; goto done; }
            }
            OcMeta wm={0};
            if (oc_metadata((int)parent,work_leaf,&wm)<0) { ok=0; goto done; }
            has_id=1; stage_dev=wm.device; stage_ino=wm.inode;
        }
        if (!h_restore) {
            long sfd=oc_openat((int)src_dir,src_leaf,OC_READ,0);
            long wfd=oc_openat((int)parent,work_leaf,OC_WRITE|OC_TRUNC,0600);
            int cok=sfd>=0 && wfd>=0;
            if (cok) {
                OcHash ch; oc_hash_init(&ch);
                oc_u8 buf[4096]; oc_u64 copied=0;
                for (;;) {
                    long r=oc_read((int)sfd,buf,sizeof buf);
                    if (r==-4) continue;
                    if (r<0) { cok=0; break; }
                    if (!r) break;
                    if (!oc_write_all((int)wfd,buf,(unsigned)r)) { cok=0; break; }
                    oc_hash_add(&ch,buf,(unsigned)r);
                    copied+=(oc_u64)r;
                    if (copied>=11) oc_cut("root_publish_partial");
                }
                char wdig[65];
                if (cok) { oc_hash_finish(&ch,wdig); cok=oc_equal(wdig,src_hash); }
                if (cok) cok=oc_fchown((int)wfd,pu,pg)>=0 && oc_mode((int)wfd,pm)>=0 && oc_sync((int)wfd)>=0;
            }
            if (sfd>=0 && oc_close((int)sfd)<0) cok=0;
            if (wfd>=0 && oc_close((int)wfd)<0) cok=0;
            if (!cok) { ok=0; goto done; }
        } else {
            long wfd=oc_openat((int)parent,work_leaf,OC_READ,0);
            char wdig[65]; OcMeta wm={0};
            int wok=wfd>=0 && oc_hash_copy((int)wfd,-1,33554432,wdig,&wm)==OC_COPY_OK &&
                oc_equal(wdig,src_hash) && oc_sync((int)wfd)>=0;
            if (wfd>=0 && oc_close((int)wfd)<0) wok=0;
            if (!wok) { ok=0; goto done; }
        }
        oc_cut("root_publish_staged");
        if (!oc_target_matches_spec((int)parent,leaf,expected_hash,expected_mode) ||
            oc_rename((int)parent,work_leaf,leaf)<0) { ok=0; goto done; }
        has_id=0;
        oc_cut("root_publish_renamed");
    }
    {
        long tfd=oc_openat((int)parent,leaf,OC_READ,0);
        int tok=tfd>=0 && oc_sync((int)tfd)>=0;
        if (tfd>=0 && oc_close((int)tfd)<0) tok=0;
        if (!tok || oc_sync((int)parent)<0) ok=0;
    }

done:
    if (has_id && !oc_absent_at((int)parent,work_leaf)) {
        OcMeta wm={0};
        if (oc_metadata((int)parent,work_leaf,&wm)>=0 && wm.device==stage_dev && wm.inode==stage_ino &&
            src_dir>=0 && oc_stage_matches_src((int)parent,work_leaf,(int)src_dir,src_leaf)) {
            if ((!oc_root_is_mode(root,1) && !oc_remount(root,root_path,1)) ||
                oc_unlink((int)parent,work_leaf)<0 || oc_sync((int)parent)<0) ok=0;
        } else ok=0;
    }
    if (!oc_root_is_mode(root,0)) {
        if (!oc_remount(root,root_path,0)) ok=0;
    }
    if (src_dir>=0 && oc_close((int)src_dir)<0) ok=0;
    if (oc_close((int)parent)<0) ok=0;
    return ok;
}

int oc_selector_matches_at(int root, const char *sel_hash, const char *sel_meta) {
    if (!sel_hash || oc_equal(sel_hash,"-"))
        return oc_absent_at(root,"usr/bin/open-connect-boot-select");
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    if (ubin<0) return 0;
    char got[65], ms[40]; OcMeta m={0};
    int ok=oc_hash_file_at((int)ubin,"open-connect-boot-select",got,&m) &&
        oc_equal(got,sel_hash) && oc_meta_mode_str(&m,ms) && oc_equal(ms,sel_meta);
    if (oc_close((int)ubin)<0) ok=0;
    return ok;
}

int oc_selector_pair_check(int root, int data_fd, const char *before_id, const char *after_id,
                           long owner, long group) {
    (void)owner; (void)group;
    OcTxnSnap *b=&oc_snap_pool[2], *a=&oc_snap_pool[3];
    if (!oc_txn_read_snap(data_fd,before_id,b) || !oc_txn_read_snap(data_fd,after_id,a)) return 0;
    if (oc_absent_at(root,"usr/bin/open-connect-boot-select"))
        return oc_equal(b->sel_hash,"-") || oc_equal(a->sel_hash,"-");
    return oc_selector_matches_at(root,b->sel_hash,b->sel_meta) || oc_selector_matches_at(root,a->sel_hash,a->sel_meta);
}

int oc_selector_apply(int root, const char *root_path, int data_fd, const char *rev,
                      const char *before_id, const char *after_id, const char *base_snap,
                      long owner, long group) {
    if (!oc_selector_pair_check(root,data_fd,before_id,after_id,owner,group)) return 0;
    OcTxnSnap *a=&oc_snap_pool[2]; char src_rel[128];
    if (!oc_txn_read_snap(data_fd,after_id,a)) return 0;
    if (oc_equal(a->sel_hash,"-")) {
        if (!oc_join(src_rel,sizeof src_rel,"","-")) return 0;
    } else {
        if (!oc_join4(src_rel,sizeof src_rel,"packages/",a->sel_pkg,"/boot-select",0)) return 0;
        char got[65]; OcMeta sm={0};
        long fd=oc_beneath(data_fd,src_rel,OC_READ,0);
        int ok=fd>=0 && oc_hash_copy((int)fd,-1,33554432,got,&sm)==OC_COPY_OK && oc_equal(got,a->sel_hash);
        if (fd>=0 && oc_close((int)fd)<0) ok=0;
        if (!ok) return 0;
    }
    char act_h[65], act_m[40];
    if (oc_absent_at(root,"usr/bin/open-connect-boot-select")) {
        if (!oc_join(act_h,sizeof act_h,"","-") || !oc_join(act_m,sizeof act_m,"","-")) return 0;
    } else {
        long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
        OcMeta m={0};
        int ok=ubin>=0 && oc_hash_file_at((int)ubin,"open-connect-boot-select",act_h,&m) &&
            oc_meta_mode_str(&m,act_m);
        if (ubin>=0 && oc_close((int)ubin)<0) ok=0;
        if (!ok) return 0;
    }
    return oc_root_publish(root,root_path,data_fd,rev,"usr/bin/open-connect-boot-select",
                           src_rel,a->sel_meta,act_h,act_m,0,0,0,base_snap,owner,group);
}

static int oc_staging_scan_cb(const char *name, void *raw) {
    if (oc_prefix(name,".open-connect-")) { *(int *)raw=1; return 0; }
    return 1;
}

int oc_startup_staging_guard(int root) {
    const char *dirs[2]={"usr/bin","etc/ssh"};
    for (unsigned i=0; i<2; ++i) {
        long d=oc_beneath(root,dirs[i],OC_DIRECTORY,0);
        if (d<0) return 0;
        int found=0;
        int ok=oc_dir_iter((int)d,oc_staging_scan_cb,&found) && !found;
        if (oc_close((int)d)<0) ok=0;
        if (!ok) return 0;
    }
    return 1;
}

int oc_startup_staging_retire(int root, const char *root_path, int data_fd, const char *rev,
                              const char *snap_id, const char *base_snap, long owner, long group) {
    OcTxnSnap *s=&oc_snap_pool[2], *b=&oc_snap_pool[3];
    if (!oc_txn_read_snap(data_fd,snap_id,s)) return 0;
    const char *names[4]={"autostart","runlogin","sshd.conf","selector"};
    const char *targets[4]={"usr/bin/autostart","usr/bin/runlogin","etc/ssh/sshd_config","usr/bin/open-connect-boot-select"};
    for (unsigned i=0; i<4; ++i) {
        char src_rel[160], hold_rel[96]; const char *hold_mode=0;
        hold_rel[0]=0;
        if (i==3) {
            if (oc_equal(s->sel_hash,"-")) continue;
            if (!oc_join4(src_rel,sizeof src_rel,"packages/",s->sel_pkg,"/boot-select",0)) return 0;
        } else {
            if (!oc_join4(src_rel,sizeof src_rel,"snapshots/",snap_id,"/",names[i])) return 0;
        }
        if (oc_absent_at(data_fd,src_rel)) continue;
        if (i==1) {
            if (!oc_txn_read_snap(data_fd,base_snap,b) || !b->has_access) return 0;
            if (!oc_equal(b->acc_f[5],"-")) {
                if (!oc_join(hold_rel,sizeof hold_rel,"usr/bin/.open-connect-runlogin-",b->acc_f[5])) return 0;
                if (oc_equal(s->login_dig,b->login_dig)) {
                    if (!oc_absent_at(root,hold_rel)) hold_mode="restore";
                    else hold_rel[0]=0;
                } else hold_mode="keep";
            }
        }
        char act_h[65], act_m[40];
        if (oc_absent_at(root,targets[i])) {
            if (!oc_join(act_h,sizeof act_h,"","-") || !oc_join(act_m,sizeof act_m,"","-")) return 0;
        } else {
            char pr[192]; const char *lf=0; OcMeta m={0};
            if (!oc_split_parent_leaf(targets[i],pr,&lf)) return 0;
            long pd=oc_beneath(root,pr,OC_DIRECTORY,0);
            int pok=pd>=0 && oc_hash_file_at((int)pd,lf,act_h,&m) && oc_meta_mode_str(&m,act_m);
            if (pd>=0 && oc_close((int)pd)<0) pok=0;
            if (!pok) return 0;
        }
        if (!oc_root_publish(root,root_path,data_fd,rev,targets[i],src_rel,"-",
                             act_h,act_m,hold_rel[0]?hold_rel:0,hold_mode,1,base_snap,owner,group))
            return 0;
    }
    return 1;
}
