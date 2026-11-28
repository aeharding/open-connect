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
#if defined(OC_HOST) || defined(OC_TEST_PINFILE)
#ifdef OC_HOST
    if (getenv("OC_HOST_REMOUNT_FAIL")) return 0;
#endif
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
#if defined(OC_HOST) || defined(OC_TEST_PINFILE)
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
#if defined(OC_HOST) || defined(OC_TEST_PINFILE)
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
                    const char *base_snap) {
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
            if (!oc_access_hold_verify(root,data_fd,base_snap)) { ok=0; goto done; }
            long hfd=oc_openat((int)parent,held_leaf,OC_READ,0);
            int hok=hfd>=0 && oc_sync((int)hfd)>=0;
            if (hfd>=0 && oc_close((int)hfd)<0) hok=0;
            if (!hok || oc_sync((int)parent)<0) { ok=0; goto done; }
        }
        if (oc_absent_at((int)parent,work_leaf)) {
            if (h_restore) {
                OcMeta hm={0}; char hms[40];
                if (!oc_access_hold_verify(root,data_fd,base_snap) ||
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

int oc_selector_pair_check(int root, int data_fd, const char *before_id, const char *after_id) {
    OcTxnSnap *b=&oc_snap_pool[2], *a=&oc_snap_pool[3];
    if (!oc_txn_read_snap(data_fd,before_id,b) || !oc_txn_read_snap(data_fd,after_id,a)) return 0;
    if (oc_absent_at(root,"usr/bin/open-connect-boot-select"))
        return oc_equal(b->sel_hash,"-") || oc_equal(a->sel_hash,"-");
    return oc_selector_matches_at(root,b->sel_hash,b->sel_meta) || oc_selector_matches_at(root,a->sel_hash,a->sel_meta);
}

int oc_selector_apply(int root, const char *root_path, int data_fd, const char *rev,
                      const char *before_id, const char *after_id, const char *base_snap) {
    if (!oc_selector_pair_check(root,data_fd,before_id,after_id)) return 0;
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
                           src_rel,a->sel_meta,act_h,act_m,0,0,0,base_snap);
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
                              const char *snap_id, const char *base_snap) {
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
                             act_h,act_m,hold_rel[0]?hold_rel:0,hold_mode,1,base_snap))
            return 0;
    }
    return 1;
}

int oc_vfat_mount_mode(int root, const char *target) {
    if (oc_text(root,"proc/self/mounts",oc_mscratch,sizeof oc_mscratch,1)<0) return 0;
    unsigned hits=0; int mode=0;
    char *p=oc_mscratch, *f[6]; int mr;
    while ((mr=oc_mounts_next(&p,f))>0) {
        if (!oc_equal(f[1],target)) continue;
        if (!oc_equal(f[2],"vfat")) return 0;
        char opts[256];
        if (!oc_join(opts,sizeof opts,",",f[3]) || !oc_join(opts,sizeof opts,opts,",")) return 0;
        int rw=0, ro=0;
        for (char *q=opts; *q; ++q) {
            if (oc_prefix(q,",rw,")) ++rw;
            if (oc_prefix(q,",ro,")) ++ro;
        }
        if (rw+ro!=1) return 0;
        mode=rw?1:2;
        ++hits;
    }
    return (mr==0 && hits==1) ? mode : 0;
}

int oc_open_single_usb_file(int root, const char *filename, oc_u64 max_size,
                            const char *not_found_err, const char *dup_err,
                            const char *bad_file_err, const char *bad_vol_err,
                            const char **err_out) {
    static const char *const vnames[4]={"sda1","sdb1","sdc1","sdd1"};
    int found_fd=-1;
    long mnt=oc_beneath(root,"tmp/mnt",OC_DIRECTORY,0);
    if (mnt<0) { *err_out=not_found_err; return -1; }
    for (unsigned i=0; i<4; ++i) {
        if (oc_absent_at((int)mnt,vnames[i])) continue;
        long vd=oc_openat((int)mnt,vnames[i],OC_DIRECTORY,0);
        if (vd<0) {
            if (found_fd>=0) (void)oc_close(found_fd);
            (void)oc_close((int)mnt); *err_out=bad_file_err; return -1;
        }
        if (oc_absent_at((int)vd,filename)) { (void)oc_close((int)vd); continue; }
        if (found_fd>=0) {
            (void)oc_close((int)vd); (void)oc_close(found_fd);
            (void)oc_close((int)mnt); *err_out=dup_err; return -1;
        }
        char vabs[32]; OcMeta vm={0}, fm={0};
        if (!oc_join(vabs,sizeof vabs,"/tmp/mnt/",vnames[i]) || !oc_vfat_mount_mode(root,vabs)) {
            (void)oc_close((int)vd); (void)oc_close((int)mnt); *err_out=bad_vol_err; return -1;
        }
        long fd=oc_openat((int)vd,filename,OC_READ,0);
        int fok=fd>=0 && oc_stat((int)vd,&vm)>=0 && oc_stat((int)fd,&fm)>=0 &&
            fm.device==vm.device && (fm.mode&OC_TYPE)==OC_REGULAR && fm.size<=max_size;
        (void)oc_close((int)vd);
        if (!fok) {
            if (fd>=0) (void)oc_close((int)fd);
            (void)oc_close((int)mnt); *err_out=bad_file_err; return -1;
        }
        found_fd=(int)fd;
    }
    (void)oc_close((int)mnt);
    if (found_fd<0) { *err_out=not_found_err; return -1; }
    return found_fd;
}

int oc_usb_remount(int root, const char *target, int rw) {
#if defined(OC_HOST) || defined(OC_TEST_PINFILE)
#ifdef OC_HOST
    if (getenv("OC_HOST_USB_REMOUNT_FAIL")) return 0;
#endif
    char *buf=oc_big_buf, *out=oc_big_buf+16384;
    int n=oc_text(root,"proc/self/mounts",buf,16384,0);
    if (n<=0) return 0;
    const char *from=rw?"ro":"rw", *to=rw?"rw":"ro";
    unsigned used=0; char *p=buf;
    while (*p) {
        char *line=p;
        while (*p && *p!='\n') ++p;
        int has_nl=(*p=='\n');
        if (has_nl) *p++=0;
        char *f[6]; unsigned nf=0;
        char lcopy[512];
        if (oc_length(line)>=sizeof lcopy) return 0;
        for (unsigned i=0; (lcopy[i]=line[i])!=0; ++i) {}
        char *lp=lcopy;
        while (*lp) {
            while (*lp==' '||*lp=='\t') ++lp;
            if (!*lp) break;
            if (nf<6) f[nf++]=lp;
            while (*lp && *lp!=' ' && *lp!='\t') ++lp;
            if (*lp) *lp++=0;
        }
        if (nf==6 && oc_equal(f[1],target) && oc_equal(f[2],"vfat")) {
            char nopts[256]; unsigned nu=0;
            char *q=f[3];
            while (*q) {
                char *tok=q; while (*q && *q!=',') ++q;
                int has_c=(*q==','); if (has_c) *q++=0;
                const char *emit=oc_equal(tok,from)?to:tok;
                unsigned el=oc_length(emit);
                if (nu+el+(has_c?1:0)>=sizeof nopts) return 0;
                for (unsigned j=0; j<el; ++j) nopts[nu++]=emit[j];
                if (has_c) nopts[nu++]=',';
            }
            nopts[nu]=0;
            char nline[512];
            if (!oc_join4(nline,sizeof nline,f[0]," ",f[1]," ") ||
                !oc_join4(nline,sizeof nline,nline,f[2]," ",nopts) ||
                !oc_join4(nline,sizeof nline,nline," ",f[4]," ") ||
                !oc_join(nline,sizeof nline,nline,f[5])) return 0;
            unsigned ll=oc_length(nline);
            if (used+ll>=16384) return 0;
            for (unsigned j=0; j<ll; ++j) out[used++]=nline[j];
        } else {
            unsigned ll=oc_length(line);
            if (used+ll>=16384) return 0;
            for (unsigned j=0; j<ll; ++j) out[used++]=line[j];
        }
        if (has_nl) { if (used+1>=16384) return 0; out[used++]='\n'; }
    }
    out[used]=0;
    long fd=oc_beneath(root,"proc/self/mounts",OC_WRITE|OC_TRUNC,0600);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,out,used);
    if (oc_close((int)fd)<0) ok=0;
    return ok && oc_vfat_mount_mode(root,target)==(rw?1:2);
#else
    char tbuf[32];
    if (!oc_join(tbuf,sizeof tbuf,target,"")) return 0;
    char *argv[]={
        "/bin/busybox","timeout","-t","8","-s","TERM",
        "/bin/busybox","mount","-i","-n","-o",
        rw?"remount,rw":"remount,ro",tbuf,0
    };
    if (oc_run_cmd("/bin/busybox",argv,-1,0,0,-1)!=0) return 0;
    return oc_vfat_mount_mode(root,target)==(rw?1:2);
#endif
}

int oc_factory_wireless(int root, const char *root_path) {
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
    int wrc=oc_run_cmd("/bin/sh",argv,-1,0,0,-1);
    return wrc<0 ? 2 : (wrc==2 ? 0 : 1);
}

static char *oc_static_val(const char *v, int allow_two) {
    if (oc_equal(v,"0")) return "0";
    if (oc_equal(v,"1")) return "1";
    if (allow_two && oc_equal(v,"2")) return "2";
    return 0;
}

/* Strict allowlisted OCPREFS1 user-toggle parser (never touches package/nvram/metadata/access). */
int oc_prefs_preset_apply(char *text, unsigned bytes, const OcCatalog *cat, OcPrefs *prefs, unsigned *changed) {
    if (!cat || !cat->count || cat->count>16 || !prefs || prefs->svc_count!=cat->count || bytes<9 || bytes>1023) return 0;
    if (oc_length(text)!=bytes) return 0;
    char *p=text;
    char *hdr=p;
    while (*p && *p!='\n') ++p;
    if (*p!='\n') return 0;
    *p++=0;
    unsigned hlen=oc_length(hdr);
    if (hlen && hdr[hlen-1]=='\r') hdr[--hlen]=0;
    if (!oc_equal(hdr,"OCPREFS1")) return 0;

    unsigned seen_scalar=0, seen_svc=0, applied=0, chg=0;
    static const char *const skeys[8]={
        "base","carplay-autoshow","hold-scroll","menu-loop","source-order","touch","warning","wireless"
    };
    char **slots[8]={
        &prefs->base,&prefs->autoshow,&prefs->hold_scroll,&prefs->menu_loop,
        &prefs->source_order,&prefs->touch,&prefs->warning,&prefs->wireless
    };
    int *has_opt[8]={0,&prefs->has_autoshow,&prefs->has_hold_scroll,&prefs->has_menu_loop,&prefs->has_source_order,0,0,0};

    while (*p) {
        char *ln=p;
        while (*p && *p!='\n') ++p;
        if (*p=='\n') *p++=0;
        unsigned llen=oc_length(ln);
        if (llen && ln[llen-1]=='\r') ln[--llen]=0;
        if (!oc_no_cntrl(ln)) return 0;
        if (!llen || ln[0]=='#') continue;
        char *eq=0;
        for (char *q=ln; *q; ++q) if (*q=='=') { if (eq) return 0; eq=q; }
        if (!eq || eq==ln || !eq[1]) return 0;
        *eq=0;
        const char *k=ln, *v=eq+1;
        int matched=0;
        for (unsigned i=0; i<8; ++i) {
            if (!oc_equal(k,skeys[i])) continue;
            if (seen_scalar&(1u<<i)) return 0;
            char *sv=oc_static_val(v,i==5);
            if (!sv) return 0;
            seen_scalar|=1u<<i;
            if (!oc_equal(*slots[i],sv)) chg|=1u<<i;
            *slots[i]=sv;
            if (has_opt[i]) *has_opt[i]=1;
            ++applied; matched=1; break;
        }
        if (matched) continue;
        if (!oc_prefix(k,"service.")) return 0;
        const char *sid=k+8;
        char *sv=oc_static_val(v,0);
        if (!sv) return 0;
        for (unsigned i=0; i<cat->count; ++i) {
            if (!oc_equal(sid,cat->rows[i].id)) continue;
            if (seen_svc&(1u<<i)) return 0;
            seen_svc|=1u<<i;
            if (!oc_equal(prefs->svc_vals[i],sv)) chg|=256u;
            prefs->svc_vals[i]=sv;
            if (oc_equal(sid,"pandora")) prefs->pandora=sv;
            ++applied; matched=1; break;
        }
        if (!matched) return 0;
    }
    if (!applied) return 0;
    if (changed) *changed=chg;
    return 1;
}

int oc_prefs_preset_write(const OcCatalog *cat, const OcPrefs *p, char *out, unsigned cap) {
    unsigned at=0;
    if (!cat || !cat->count || cat->count>16 || cat->count!=p->svc_count) return 0;
    if (!oc_append(out,cap,&at,"OCPREFS1\nbase=") || !oc_append(out,cap,&at,p->base) ||
        !oc_append(out,cap,&at,"\ncarplay-autoshow=") || !oc_append(out,cap,&at,p->autoshow) ||
        !oc_append(out,cap,&at,"\nhold-scroll=") || !oc_append(out,cap,&at,p->hold_scroll) ||
        !oc_append(out,cap,&at,"\nmenu-loop=") || !oc_append(out,cap,&at,p->menu_loop)) return 0;
    for (unsigned i=0; i<cat->count; ++i) {
        if (!oc_append(out,cap,&at,"\nservice.") || !oc_append(out,cap,&at,cat->rows[i].id) ||
            !oc_append(out,cap,&at,"=") || !oc_append(out,cap,&at,p->svc_vals[i])) return 0;
    }
    if (!oc_append(out,cap,&at,"\nsource-order=") || !oc_append(out,cap,&at,p->source_order) ||
        !oc_append(out,cap,&at,"\ntouch=") || !oc_append(out,cap,&at,p->touch) ||
        !oc_append(out,cap,&at,"\nwarning=") || !oc_append(out,cap,&at,p->warning) ||
        !oc_append(out,cap,&at,"\nwireless=") || !oc_append(out,cap,&at,p->wireless) ||
        !oc_append(out,cap,&at,"\n")) return 0;
    return at<=1023;
}
