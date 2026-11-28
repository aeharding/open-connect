/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native developer access management: public-key import, runlogin/sshd_config
 * composition, original runlogin hardlink hold verification & cleanup, and
 * transactional pair check/apply.
 */
#include "oc-core.h"
#ifdef OC_HOST
#include <stdlib.h>
#endif

int oc_access_key_verify(int data_fd, const char *key_id, long owner, long group) {
    if (!oc_hex(key_id,64)) return 0;
    int kdir=oc_open_private(data_fd,"keys");
    if (kdir<0) return 0;
    char fname[80], dig[65]; OcMeta m={0};
    int ok=oc_join(fname,sizeof fname,key_id,".cmu") &&
        oc_hash_file_at(kdir,fname,dig,&m) && m.mode==(OC_REGULAR|0600) &&
        m.uid==(unsigned)owner && m.gid==(unsigned)group && oc_equal(dig,key_id);
    if (oc_close(kdir)<0) ok=0;
    return ok;
}

static int oc_b64_ok(const char *s) {
    if (!*s) return 0;
    for (const char *p=s; *p; ++p) {
        unsigned char c=(unsigned char)*p;
        if (!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='+'||c=='/'||c=='=')) return 0;
    }
    return 1;
}

int oc_access_key_import(int root, const char *root_path, int data_fd, long owner, long group,
                         char out_id[65], const char **err_out) {
    int pub_fd=oc_open_single_usb_file(root,"open-connect.pub",8192,"public_key_not_found",
                                       "multiple_public_keys","invalid_public_key","invalid_key_volume",err_out);
    if (pub_fd<0) return 0;
    char *raw=oc_big_buf, *clean=oc_big_buf+16384;
    int n=oc_text_fd(pub_fd,raw,8193);
    if (oc_close(pub_fd)<0 || n<=0) { *err_out="unsupported_public_key"; return 0; }

    /* Extract single non-empty line: <type> <base64> [comment]. */
    char *type=0, *blob=0; unsigned lines=0; char *p=raw;
    while (*p) {
        char *ln=p;
        while (*p && *p!='\n') ++p;
        if (*p=='\n') *p++=0;
        unsigned ll=oc_length(ln);
        if (ll && ln[ll-1]=='\r') ln[--ll]=0;
        while (*ln==' '||*ln=='\t') ++ln;
        if (!*ln) continue;
        if (++lines!=1) { *err_out="unsupported_public_key"; return 0; }
        type=ln;
        while (*ln && *ln!=' ' && *ln!='\t') ++ln;
        if (!*ln) { *err_out="unsupported_public_key"; return 0; }
        *ln++=0;
        while (*ln==' '||*ln=='\t') ++ln;
        blob=ln;
        while (*ln && *ln!=' ' && *ln!='\t') ++ln;
        *ln=0;
    }
    if (lines!=1 || !type || !blob || !oc_b64_ok(blob) ||
        !(oc_equal(type,"ssh-rsa")||oc_equal(type,"ecdsa-sha2-nistp256")||
          oc_equal(type,"ecdsa-sha2-nistp384")||oc_equal(type,"ecdsa-sha2-nistp521"))) {
        *err_out="unsupported_public_key"; return 0;
    }
    if (!oc_join4(clean,8192,type," ",blob,"\n")) { *err_out="unsupported_public_key"; return 0; }

    int kdir=oc_open_private(data_fd,"keys");
    if (kdir<0) { *err_out="invalid_key_directory"; return 0; }
    char nonce[33], wname[48], dbase[320], wabs[400];
    if (!oc_random(root,nonce) || !oc_join(wname,sizeof wname,".new-",nonce) ||
        !oc_new_text(kdir,wname,clean,0600)) {
        (void)oc_close(kdir); *err_out="key_create_failed"; return 0;
    }
    const char *kerr=0; int keep_w=0;
    char id[65], fname[80], info[256];
    if (!oc_data_base(root_path,dbase,sizeof dbase) ||
        !oc_join4(wabs,sizeof wabs,dbase,"/keys/",wname,0)) { kerr="key_create_failed"; goto kdone; }

    const char *keygen="/usr/bin/ssh-keygen";
#ifdef OC_HOST
    const char *kg_env=getenv("OC_HOST_SSH_KEYGEN");
    if (kg_env && *kg_env) keygen=kg_env;
#endif
    char *kargv[]={(char *)keygen,"-l","-f",wabs,0};
    if (oc_run_cmd(keygen,kargv,-1,info,sizeof info,-1)!=0) { kerr="invalid_public_key"; goto kdone; }
    char *sp=info; while (*sp && *sp!=' ' && *sp!='\t' && *sp!='\n') ++sp;
    *sp=0;
    oc_u64 bits=0;
    if (!oc_decimal(info,&bits)) { kerr="invalid_public_key"; goto kdone; }
    if (oc_equal(type,"ssh-rsa") && bits<2048) { kerr="weak_public_key"; goto kdone; }

    OcMeta wm={0};
    long wfd=oc_openat(kdir,wname,OC_READ,0);
    int ok=wfd>=0 && oc_hash_copy((int)wfd,-1,8192,id,&wm)==OC_COPY_OK &&
        oc_mode((int)wfd,0600)>=0 && oc_sync((int)wfd)>=0;
    if (wfd>=0 && oc_close((int)wfd)<0) ok=0;
    if (!ok || !oc_join(fname,sizeof fname,id,".cmu")) { kerr="key_hash_failed"; goto kdone; }
    if (oc_absent_at(kdir,fname)) {
        if (oc_rename(kdir,wname,fname)<0) { kerr="key_publish_failed"; goto kdone; }
        keep_w=1;
    } else {
        (void)oc_unlink(kdir,wname); keep_w=1;
        if (!oc_access_key_verify(data_fd,id,owner,group)) { kerr="key_changed"; goto kdone; }
    }
    long ffd=oc_openat(kdir,fname,OC_READ,0);
    ok=ffd>=0 && oc_sync((int)ffd)>=0;
    if (ffd>=0 && oc_close((int)ffd)<0) ok=0;
    if (ok) ok=oc_sync(kdir)>=0;
    if (!ok) kerr="key_publish_failed";
kdone:
    if (!keep_w) (void)oc_unlink(kdir,wname);
    if (oc_close(kdir)<0 && !kerr) kerr="key_publish_failed";
    if (kerr) { *err_out=kerr; return 0; }
    return oc_join(out_id,65,"",id);
}

static int oc_lower_eq(const char *a, const char *b) {
    while (*a && *b) {
        char ca=*a++, cb=*b++;
        if (ca>='A'&&ca<='Z') ca=(char)(ca+32);
        if (ca!=cb) return 0;
    }
    return *a==0 && *b==0;
}

static int oc_passwd_uid0_is_cmu(int root) {
    if (oc_text(root,"etc/passwd",oc_mscratch,sizeof oc_mscratch,0)<=0) return 0;
    unsigned hits=0; char *p=oc_mscratch;
    while (*p) {
        char *ln=p;
        while (*p && *p!='\n') ++p;
        if (*p=='\n') *p++=0;
        char *f[7]; unsigned n=0; char *q=ln;
        while (n<7) {
            f[n++]=q;
            while (*q && *q!=':') ++q;
            if (!*q) break;
            *q++=0;
        }
        if (n>=3 && oc_equal(f[2],"0")) {
            if (!oc_equal(f[0],"cmu")) return 0;
            ++hits;
        }
    }
    return hits==1;
}

int oc_access_compose(int root, const char *root_path, int data_fd, const char *session_dir,
                      const char *base_snap, const char *console_dig, int work_fd,
                      const char *work_leaf, const char *uart, const char *ssh, const char *key,
                      long owner, long group) {
    OcTxnSnap *base=&oc_snap_pool[2];
    if (!oc_txn_read_snap(data_fd,base_snap,base) || !base->has_access) return 0;
    if (!oc_bit(uart) || !oc_bit(ssh)) return 0;
    if (!oc_equal(key,"-") && !oc_access_key_verify(data_fd,key,owner,group)) return 0;
    int bdir=oc_open_sub(data_fd,"snapshots",base_snap);
    if (bdir<0) return 0;

    int ok=1;
    if (oc_equal(uart,"1")) {
        char cdig[65];
        long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
        ok=sdir>=0 && console_dig && oc_hex(console_dig,64) &&
            oc_copy_file_at((int)sdir,"console.sh",work_fd,"runlogin",0600,0,0,cdig) &&
            oc_equal(cdig,console_dig);
        if (sdir>=0 && oc_close((int)sdir)<0) ok=0;
    } else {
        ok=oc_copy_file_at(bdir,"runlogin",work_fd,"runlogin",0600,0,0,0);
    }

    if (ok && oc_equal(ssh,"1")) {
        char *src=oc_big_buf, *dst=oc_big_buf+16384;
        if (!oc_access_key_verify(data_fd,key,owner,group) || !oc_passwd_uid0_is_cmu(root) ||
            oc_text(bdir,"sshd.conf",src,16384,0)<=0) { ok=0; }
        else {
            unsigned used=0, auth_hits=0; char *p=src;
            while (ok && *p) {
                char *ln=p;
                while (*p && *p!='\n') ++p;
                int has_nl=(*p=='\n');
                if (has_nl) *p++=0;
                char *w=ln; while (*w==' '||*w=='\t') ++w;
                char tok[32]; unsigned tl=0;
                while (w[tl] && w[tl]!=' ' && w[tl]!='\t' && tl+1<sizeof tok) { tok[tl]=w[tl]; ++tl; }
                tok[tl]=0;
                if (oc_lower_eq(tok,"match")) { ok=0; break; }
                unsigned ll=oc_length(ln);
                if (oc_lower_eq(tok,"authorizedkeysfile")) {
                    for (unsigned i=0; i<ll; ++i) if (ln[i]=='#') { ok=0; break; }
                    if (!ok) break;
                    ++auth_hits;
                    char extra[128];
                    if (!oc_join4(extra,sizeof extra," /data_persist/open-connect/keys/",key,".%u",0)) { ok=0; break; }
                    unsigned el=oc_length(extra);
                    if (used+ll+el+1>=16384) { ok=0; break; }
                    for (unsigned i=0; i<ll; ++i) dst[used++]=ln[i];
                    for (unsigned i=0; i<el; ++i) dst[used++]=extra[i];
                } else {
                    if (used+ll+1>=16384) { ok=0; break; }
                    for (unsigned i=0; i<ll; ++i) dst[used++]=ln[i];
                }
                if (has_nl) dst[used++]='\n';
            }
            dst[used]=0;
            if (ok) ok=auth_hits==1 && oc_new_text(work_fd,"sshd.conf",dst,0600);
        }
    } else if (ok) {
        ok=oc_copy_file_at(bdir,"sshd.conf",work_fd,"sshd.conf",0600,0,0,0);
    }
    if (oc_close(bdir)<0) ok=0;
    if (!ok) return 0;

    /* Validate generated sshd.conf with sshd -t -f. */
    const char *sshd="/usr/sbin/sshd";
#ifdef OC_HOST
    const char *sd_env=getenv("OC_HOST_SSHD");
    if (sd_env && *sd_env) sshd=sd_env;
#endif
    char dbase[320], sshd_path[448];
    if (!oc_data_base(root_path,dbase,sizeof dbase) ||
        !oc_join4(sshd_path,sizeof sshd_path,dbase,"/",work_leaf,"/sshd.conf")) return 0;
    char *sargv[]={(char *)sshd,"-t","-f",sshd_path,0};
    if (oc_run_cmd(sshd,sargv,-1,0,0,-1)!=0) return 0;

    char acc_line[320];
    if (!oc_join4(acc_line,sizeof acc_line,uart,"|",ssh,"|") ||
        !oc_join4(acc_line,sizeof acc_line,acc_line,key,"|",base->acc_f[3]) ||
        !oc_join4(acc_line,sizeof acc_line,acc_line,"|",base->acc_f[4],"|") ||
        !oc_join4(acc_line,sizeof acc_line,acc_line,base->acc_f[5],"\n",0)) return 0;
    return oc_new_text(work_fd,"access",acc_line,0600);
}

int oc_access_hold_verify(int root, int data_fd, const char *base_snap) {
    OcTxnSnap *base=&oc_snap_pool[6];
    if (!oc_txn_read_snap(data_fd,base_snap,base) || !base->has_access || oc_equal(base->acc_f[5],"-")) return 0;
    oc_u64 want_ino=0;
    if (!oc_decimal(base->acc_f[5],&want_ino)) return 0;
    char hleaf[64];
    if (!oc_join(hleaf,sizeof hleaf,".open-connect-runlogin-",base->acc_f[5])) return 0;
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    if (ubin<0) return 0;
    OcMeta hm={0}, rm={0}; char hdig[65], hms[40];
    int ok=oc_metadata((int)ubin,"runlogin",&rm)>=0 &&
        oc_hash_file_at((int)ubin,hleaf,hdig,&hm) && hm.inode==want_ino && hm.device==rm.device &&
        oc_equal(hdig,base->login_dig) && oc_meta_mode_str(&hm,hms) && oc_equal(hms,base->acc_f[3]);
    if (oc_close((int)ubin)<0) ok=0;
    return ok;
}

int oc_access_login_check(int root, int data_fd, const char *base_snap) {
    OcTxnSnap *base=&oc_snap_pool[5];
    if (!oc_txn_read_snap(data_fd,base_snap,base)) return 0;
    if (!base->has_access || oc_equal(base->acc_f[5],"-")) return 1;
    oc_u64 want_ino=0;
    if (!oc_decimal(base->acc_f[5],&want_ino)) return 0;
    char hleaf[64];
    if (!oc_join(hleaf,sizeof hleaf,".open-connect-runlogin-",base->acc_f[5])) return 0;
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    if (ubin<0) return 0;
    int ok=1;
    if (!oc_absent_at((int)ubin,hleaf)) ok=oc_access_hold_verify(root,data_fd,base_snap);
    char cur_dig[65]; OcMeta rm={0};
    if (ok) ok=oc_hash_file_at((int)ubin,"runlogin",cur_dig,&rm);
    if (oc_close((int)ubin)<0) ok=0;
    if (!ok) return 0;
    if (oc_equal(cur_dig,base->login_dig)) return rm.inode==want_ino;
    return oc_access_hold_verify(root,data_fd,base_snap);
}

int oc_access_hold_cleanup(int root, const char *root_path, int data_fd, const char *base_snap) {
    OcTxnSnap *base=&oc_snap_pool[5];
    if (!oc_txn_read_snap(data_fd,base_snap,base)) return 0;
    if (!base->has_access || oc_equal(base->acc_f[5],"-")) return 1;
    oc_u64 want_ino=0;
    if (!oc_decimal(base->acc_f[5],&want_ino)) return 0;
    char hleaf[64];
    if (!oc_join(hleaf,sizeof hleaf,".open-connect-runlogin-",base->acc_f[5])) return 0;
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    if (ubin<0) return 0;
    OcMeta rm={0};
    int ok=oc_metadata((int)ubin,"runlogin",&rm)>=0 && rm.inode==want_ino;
    int remounted=0;
    if (ok && !oc_absent_at((int)ubin,hleaf)) {
        ok=oc_access_hold_verify(root,data_fd,base_snap) && oc_remount(root,root_path,1);
        if (ok) { remounted=1; ok=oc_unlink((int)ubin,hleaf)>=0; }
    }
    if (ok) ok=oc_sync((int)ubin)>=0;
    if (remounted && !oc_remount(root,root_path,0)) ok=0;
    if (oc_close((int)ubin)<0) ok=0;
    return ok;
}

int oc_access_files_match(int root, int data_fd, const char *snap_id, long owner, long group) {
    OcTxnSnap *s=&oc_snap_pool[4];
    if (!oc_txn_read_snap(data_fd,snap_id,s)) return 0;
    if (!s->has_access) return 1;
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    long essh=oc_beneath(root,"etc/ssh",OC_DIRECTORY,0);
    char ldig[65], sdig[65], lms[40], sms[40]; OcMeta lm={0}, sm={0};
    int ok=ubin>=0 && essh>=0 &&
        oc_hash_file_at((int)ubin,"runlogin",ldig,&lm) && oc_equal(ldig,s->login_dig) &&
        oc_meta_mode_str(&lm,lms) && oc_equal(lms,s->acc_f[3]) &&
        oc_hash_file_at((int)essh,"sshd_config",sdig,&sm) && oc_equal(sdig,s->ssh_dig) &&
        oc_meta_mode_str(&sm,sms) && oc_equal(sms,s->acc_f[4]);
    if (ubin>=0 && oc_close((int)ubin)<0) ok=0;
    if (essh>=0 && oc_close((int)essh)<0) ok=0;
    if (ok && !oc_equal(s->acc_f[2],"-")) ok=oc_access_key_verify(data_fd,s->acc_f[2],owner,group);
    return ok;
}

int oc_access_targets_match(int root, int data_fd, const char *snap_id, const char *base_snap,
                            long owner, long group) {
    OcTxnSnap *s=&oc_snap_pool[3];
    if (!oc_txn_read_snap(data_fd,snap_id,s)) return 0;
    if (!s->has_access) return 1;
    return oc_access_files_match(root,data_fd,snap_id,owner,group) &&
        oc_access_login_check(root,data_fd,base_snap);
}

int oc_access_pair_check(int root, int data_fd, const char *before_id, const char *after_id,
                         const char *base_snap, long owner, long group) {
    OcTxnSnap *b=&oc_snap_pool[3], *a=&oc_snap_pool[4];
    if (!oc_txn_read_snap(data_fd,before_id,b) || !oc_txn_read_snap(data_fd,after_id,a)) return 0;
    if (!b->has_access && !a->has_access) return 1;
    if (!b->has_access || !a->has_access) return 0;
    if (!oc_equal(a->acc_f[2],"-") && !oc_access_key_verify(data_fd,a->acc_f[2],owner,group)) return 0;
    if (!oc_access_login_check(root,data_fd,base_snap)) return 0;
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    long essh=oc_beneath(root,"etc/ssh",OC_DIRECTORY,0);
    char ldig[65], sdig[65], lms[40], sms[40]; OcMeta lm={0}, sm={0};
    int ok=ubin>=0 && essh>=0 &&
        oc_hash_file_at((int)ubin,"runlogin",ldig,&lm) && oc_meta_mode_str(&lm,lms) &&
        ((oc_equal(ldig,b->login_dig)&&oc_equal(lms,b->acc_f[3]))||(oc_equal(ldig,a->login_dig)&&oc_equal(lms,a->acc_f[3]))) &&
        oc_hash_file_at((int)essh,"sshd_config",sdig,&sm) && oc_meta_mode_str(&sm,sms) &&
        ((oc_equal(sdig,b->ssh_dig)&&oc_equal(sms,b->acc_f[4]))||(oc_equal(sdig,a->ssh_dig)&&oc_equal(sms,a->acc_f[4])));
    if (ubin>=0 && oc_close((int)ubin)<0) ok=0;
    if (essh>=0 && oc_close((int)essh)<0) ok=0;
    return ok;
}

int oc_access_pair_apply(int root, const char *root_path, int data_fd, const char *rev,
                         const char *before_id, const char *after_id, const char *base_snap,
                         int prepared_same_rev, long owner, long group) {
    OcTxnSnap *a=&oc_snap_pool[2], *b=&oc_snap_pool[3], *base=&oc_snap_pool[4];
    if (!oc_txn_read_snap(data_fd,after_id,a)) return 0;
    if (!a->has_access) return 1;
    if (!oc_access_pair_check(root,data_fd,before_id,after_id,base_snap,owner,group)) return 0;
    if (!oc_txn_read_snap(data_fd,before_id,b) || !oc_txn_read_snap(data_fd,base_snap,base)) return 0;

    const char *targets[2]={"usr/bin/runlogin","etc/ssh/sshd_config"};
    const char *parents[2]={"usr/bin","etc/ssh"};
    const char *leaves[2]={"runlogin","sshd_config"};
    const char *sn_names[2]={"runlogin","sshd.conf"};
    const char *bhashes[2]={b->login_dig,b->ssh_dig}, *ahashes[2]={a->login_dig,a->ssh_dig};
    const char *bmodes[2]={b->acc_f[3],b->acc_f[4]}, *amodes[2]={a->acc_f[3],a->acc_f[4]};

    for (unsigned i=0; i<2; ++i) {
        long pdir=oc_beneath(root,parents[i],OC_DIRECTORY,0);
        char act_h[65], act_m[40]; OcMeta m={0};
        int ok=pdir>=0 && oc_hash_file_at((int)pdir,leaves[i],act_h,&m) && oc_meta_mode_str(&m,act_m);
        if (pdir>=0 && oc_close((int)pdir)<0) ok=0;
        if (!ok) return 0;
        if (!((oc_equal(act_h,bhashes[i])&&oc_equal(act_m,bmodes[i])) ||
              (oc_equal(act_h,ahashes[i])&&oc_equal(act_m,amodes[i])))) return 0;
        char stg[128];
        if (!oc_join4(stg,sizeof stg,parents[i],"/.open-connect-",rev,"-") ||
            !oc_join(stg,sizeof stg,stg,leaves[i])) return 0;
        if (prepared_same_rev && oc_equal(bhashes[i],ahashes[i]) && oc_equal(bmodes[i],amodes[i]) &&
            oc_equal(act_h,ahashes[i]) && oc_equal(act_m,amodes[i]) &&
            oc_absent_at(root,stg) && oc_mounts_mode(root,oc_mscratch,sizeof oc_mscratch,0)) continue;
        char src_rel[160], hold_rel[96]; const char *hold_mode=0;
        hold_rel[0]=0;
        if (!oc_join4(src_rel,sizeof src_rel,"snapshots/",after_id,"/",sn_names[i])) return 0;
        if (i==0 && base->has_access && !oc_equal(base->acc_f[5],"-")) {
            if (!oc_join(hold_rel,sizeof hold_rel,"usr/bin/.open-connect-runlogin-",base->acc_f[5])) return 0;
            if (oc_equal(ahashes[0],base->login_dig)) {
                if (!oc_absent_at(root,hold_rel)) hold_mode="restore";
                else hold_rel[0]=0;
            } else hold_mode="keep";
        }
        if (!oc_root_publish(root,root_path,data_fd,rev,targets[i],src_rel,amodes[i],
                             act_h,act_m,hold_rel[0]?hold_rel:0,hold_mode,0,base_snap))
            return 0;
    }
    return 1;
}
