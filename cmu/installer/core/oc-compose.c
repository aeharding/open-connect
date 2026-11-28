/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native cold USB installer and firmware composer: originals backup, package
 * save, ELF/XML/HTML/SM/autostart composition, dependency capture, and full
 * transactional install/upgrade/reinstall.
 */
#include "oc-core.h"

static struct {
    char io[32768];
    char line[4096];
    char out[4608];
    char mf[8192];
    char cat[16384];
    char names[80][64];
} cm;

static __attribute__((noinline)) int cerr(const char **out, const char *e) { *out=e; return 0; }

static int oc_cstr_cmp(const char *a, const char *b) {
    while (*a && *a==*b) { ++a; ++b; }
    return (int)(unsigned char)*a - (int)(unsigned char)*b;
}

static char *oc_cfind(char *s, const char *sub) {
    for (; *s; ++s) if (oc_prefix(s,sub)) return s;
    return 0;
}

/* ---------- Streaming line reader ---------- */
typedef struct { int fd; char buf[4096]; unsigned at, filled, total, limit; } OcCStream;

static int oc_cstream_line(OcCStream *s, char *out, unsigned cap, int *had_nl) {
    unsigned n=0; *had_nl=0;
    for (;;) {
        if (s->at==s->filled) {
            long r=oc_read(s->fd,s->buf,sizeof s->buf);
            if (r==-4) continue;
            if (r<0) return -1;
            if (!r) { out[n]=0; return n?1:0; }
            s->at=0; s->filled=(unsigned)r;
        }
        char c=s->buf[s->at++];
        if (++s->total > s->limit) return -1;
        if (c=='\n') { out[n]=0; *had_nl=1; return 1; }
        if (n+1>=cap) return -1;
        out[n++]=c;
    }
}

/* ---------- Originals & stock dependency verification ---------- */
static const char *oc_orig_pin(int idx) {
    if (idx==0) return oc_pin_digest("originals/autostart",oc_orig_autostart_digest);
    char k[48];
    if (!oc_join(k,sizeof k,"root/",oc_root_names[idx-1])) return oc_root_digests[idx-1];
    return oc_pin_digest(k,oc_root_digests[idx-1]);
}

static const char *oc_orig_name(int idx) { return idx==0 ? "autostart" : oc_root_names[idx-1]; }
static const char *oc_orig_path(int idx) { return idx==0 ? "/usr/bin/autostart" : oc_root_paths[idx-1]; }

int oc_originals_verify(int data_fd) {
    int orig=oc_open_private(data_fd,"originals");
    if (orig<0) return 0;
    int ok=1;
    for (int i=0; ok && i<11; ++i)
        ok=oc_verify_file_sha(orig,oc_orig_name(i),oc_orig_pin(i),33554432);
    if (oc_close(orig)<0) ok=0;
    return ok;
}

static int oc_originals_save(int root, int data_fd, const char **err_out) {
    if (!oc_absent_at(data_fd,"originals"))
        return oc_originals_verify(data_fd) ? 1 : cerr(err_out,"originals_changed");
    char nonce[33], wleaf[48];
    if (!oc_random(root,nonce) || !oc_join(wleaf,sizeof wleaf,".originals-",nonce) ||
        oc_mkdir(data_fd,wleaf,0700)<0) return cerr(err_out,"backup_create_failed");
    int wfd=oc_open_private(data_fd,wleaf);
    if (wfd<0) { oc_rm_subdir(data_fd,wleaf); return cerr(err_out,"backup_create_failed"); }
    int ok=1;
    for (int i=0; ok && i<11; ++i) {
        const char *pin=oc_orig_pin(i);
        const char *rp=oc_orig_path(i)+1;
        long sfd=oc_beneath(root,rp,OC_READ,0);
        long dfd=sfd>=0 ? oc_openat(wfd,oc_orig_name(i),OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600) : -1;
        char dig[65]; OcMeta sm={0};
        ok=sfd>=0 && dfd>=0 && oc_hash_copy((int)sfd,(int)dfd,33554432,dig,&sm)==OC_COPY_OK &&
            oc_equal(dig,pin) && oc_mode((int)dfd,0600)>=0 && oc_sync((int)dfd)>=0;
        if (sfd>=0 && oc_close((int)sfd)<0) ok=0;
        if (dfd>=0 && oc_close((int)dfd)<0) ok=0;
        if (ok) ok=oc_verify_file_sha(wfd,oc_orig_name(i),pin,33554432);
    }
    if (ok) ok=oc_sync(wfd)>=0;
    if (oc_close(wfd)<0) ok=0;
    if (!ok) { oc_rm_subdir(data_fd,wleaf); return cerr(err_out,"backup_failed"); }
    if (oc_rename(data_fd,wleaf,"originals")<0 || oc_sync(data_fd)<0) {
        oc_rm_subdir(data_fd,wleaf); return cerr(err_out,"backup_publish_failed");
    }
    return oc_originals_verify(data_fd) ? 1 : cerr(err_out,"originals_changed");
}

static int oc_stock_dependencies_ok(int root) {
    for (unsigned i=0; i<19; ++i) {
        char k[48], dig[65]; OcMeta m={0};
        if (!oc_join(k,sizeof k,"root/",oc_root_names[i])) return 0;
        const char *pin=oc_pin_digest(k,oc_root_digests[i]);
        long fd=oc_beneath(root,oc_root_paths[i]+1,OC_READ,0);
        int ok=fd>=0 && oc_hash_copy((int)fd,-1,33554432,dig,&m)==OC_COPY_OK && oc_equal(dig,pin);
        if (fd>=0 && oc_close((int)fd)<0) ok=0;
        if (!ok) return 0;
    }
    return 1;
}

static int oc_verify_dir_manifest(int dir, OcManifest *mf, char *buf, unsigned cap) {
    if (oc_text(dir,"files.sha256",buf,cap,0)<=0 || !oc_manifest(buf,mf,0)) return 0;
    for (unsigned i=0; i<mf->count; ++i)
        if (!oc_verify_file_sha(dir,mf->rows[i].name,mf->rows[i].digest,33554432)) return 0;
    return 1;
}

/* ---------- Package save ---------- */
static int oc_package_save(int root, int data_fd, const char *session_dir,
                           char pkg_out[65], const char **err_out) {
    long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
    if (sdir<0) return cerr(err_out,"damaged_source_package");
    OcManifest smf;
    if (!oc_verify_dir_manifest((int)sdir,&smf,cm.mf,sizeof cm.mf)) {
        (void)oc_close((int)sdir); return cerr(err_out,"damaged_source_package");
    }
    int pkgs=oc_open_private(data_fd,"packages");
    if (pkgs<0) { (void)oc_close((int)sdir); return cerr(err_out,"package_create_failed"); }
    char nonce[33], wleaf[48];
    if (!oc_random(root,nonce) || !oc_join(wleaf,sizeof wleaf,".new-",nonce) ||
        oc_mkdir(pkgs,wleaf,0700)<0) {
        (void)oc_close(pkgs); (void)oc_close((int)sdir); return cerr(err_out,"package_create_failed");
    }
    int wfd=oc_open_private(pkgs,wleaf);
    long mfd=wfd>=0 ? oc_openat(wfd,"files.sha256",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600) : -1;
    int ok=wfd>=0 && mfd>=0;
    OcHash mh; oc_hash_init(&mh);
    for (unsigned i=0; ok && i<smf.count; ++i) {
        const char *nm=smf.rows[i].name;
        if (oc_equal(nm,"INSTANCE")) continue;
        unsigned mode=(oc_equal(nm,"api")||oc_equal(nm,"flush")||oc_equal(nm,"boot-select")||
                       oc_equal(nm,"ignition")||oc_equal(nm,"install")) ? 0700 : 0600;
        char dig[65], row[160];
        ok=oc_copy_file_at((int)sdir,nm,wfd,nm,mode,1,1,dig) && oc_equal(dig,smf.rows[i].digest) &&
            oc_join4(row,sizeof row,dig,"  ",nm,"\n") && oc_write_all((int)mfd,row,oc_length(row));
        if (ok) oc_hash_add(&mh,row,oc_length(row));
    }
    (void)oc_close((int)sdir);
    if (ok) {
        char inst[33], inst_ln[35], idig[65], row[160]; OcMeta im={0};
        ok=oc_random(root,inst) && oc_join(inst_ln,sizeof inst_ln,inst,"\n") &&
            oc_new_text(wfd,"INSTANCE",inst_ln,0600);
        long ifd=ok?oc_openat(wfd,"INSTANCE",OC_READ,0):-1;
        if (ok) ok=ifd>=0 && oc_hash_copy((int)ifd,-1,64,idig,&im)==OC_COPY_OK && oc_sync((int)ifd)>=0;
        if (ifd>=0 && oc_close((int)ifd)<0) ok=0;
        if (ok) ok=oc_join(row,sizeof row,idig,"  INSTANCE\n") && oc_write_all((int)mfd,row,oc_length(row));
        if (ok) oc_hash_add(&mh,row,oc_length(row));
    }
    char pkg_id[65]; pkg_id[0]=0;
    if (ok) {
        oc_hash_finish(&mh,pkg_id);
        ok=oc_mode((int)mfd,0600)>=0 && oc_sync((int)mfd)>=0;
    }
    if (mfd>=0 && oc_close((int)mfd)<0) ok=0;
    if (ok && wfd>=0) ok=oc_sync(wfd)>=0;
    if (wfd>=0 && oc_close(wfd)<0) ok=0;
    if (!ok) { oc_rm_subdir(pkgs,wleaf); (void)oc_close(pkgs); return cerr(err_out,"package_failed"); }
    if (!oc_absent_at(pkgs,pkg_id)) {
        oc_rm_subdir(pkgs,wleaf); (void)oc_close(pkgs); return cerr(err_out,"package_collision");
    }
    ok=oc_rename(pkgs,wleaf,pkg_id)>=0 && oc_sync(pkgs)>=0;
    if (!ok) oc_rm_subdir(pkgs,wleaf);
    if (oc_close(pkgs)<0) ok=0;
    if (!ok) return cerr(err_out,"package_publish_failed");
    return oc_join(pkg_out,65,"",pkg_id) ? 1 : cerr(err_out,"package_failed");
}

/* ---------- Binary patching helpers ---------- */
static int oc_copy_exact_bytes(int sfd, int dfd, unsigned count) {
    unsigned left=count;
    while (left) {
        unsigned chunk=left<sizeof cm.io ? left : (unsigned)sizeof cm.io;
        long r=oc_read(sfd,cm.io,chunk);
        if (r==-4) continue;
        if (r<=0) return 0;
        if (!oc_write_all(dfd,cm.io,(unsigned)r)) return 0;
        left-=(unsigned)r;
    }
    return 1;
}

static int oc_patch_blob_at(int out_fd, unsigned out_size, int pkg_fd, const char *blob_name,
                            unsigned offset, unsigned exact_len) {
    long bfd=oc_openat(pkg_fd,blob_name,OC_READ,0);
    if (bfd<0) return 0;
    OcMeta bm={0};
    int ok=oc_stat((int)bfd,&bm)>=0 && (bm.mode&OC_TYPE)==OC_REGULAR &&
        bm.size>0 && bm.size<=sizeof cm.io &&
        (!exact_len || bm.size==exact_len) &&
        (oc_u64)offset+bm.size<=(oc_u64)out_size;
    unsigned got=0;
    while (ok && got<(unsigned)bm.size) {
        long r=oc_read((int)bfd,cm.io+got,(unsigned)bm.size-got);
        if (r==-4) continue;
        if (r<=0) { ok=0; break; }
        got+=(unsigned)r;
    }
    if (oc_close((int)bfd)<0) ok=0;
    if (ok) ok=oc_seek_set(out_fd,offset)==(long)offset && oc_write_all(out_fd,cm.io,got);
    return ok;
}

static int oc_compose_uia(int pkg_fd, int orig_fd, int work_fd) {
    const unsigned head_n=456604u, gap_n=32768u, tail_n=217443u;
    const unsigned orig_total=head_n+tail_n, out_total=orig_total+gap_n;
    long sfd=oc_openat(orig_fd,"uia.so",OC_READ,0);
    if (sfd<0) return 0;
    OcMeta sm={0};
    if (oc_stat((int)sfd,&sm)<0 || (sm.mode&OC_TYPE)!=OC_REGULAR || sm.size!=orig_total) {
        (void)oc_close((int)sfd); return 0;
    }
    long ofd=oc_openat(work_fd,"uia.so",OC_RW|OC_CREATE|OC_EXCLUSIVE,0600);
    if (ofd<0) { (void)oc_close((int)sfd); return 0; }
    int ok=oc_copy_exact_bytes((int)sfd,(int)ofd,head_n);
    if (ok) {
        for (unsigned i=0; i<gap_n; ++i) cm.io[i]=0;
        ok=oc_write_all((int)ofd,cm.io,gap_n) && oc_copy_exact_bytes((int)sfd,(int)ofd,tail_n);
    }
    if (oc_close((int)sfd)<0) ok=0;
    if (ok) ok=oc_patch_blob_at((int)ofd,out_total,pkg_fd,"native.bin",456604u,0) &&
        oc_patch_blob_at((int)ofd,out_total,pkg_fd,"branch.bin",49076u,0) &&
        oc_patch_blob_at((int)ofd,out_total,pkg_fd,"sizes.bin",68u,0);
    if (ok) {
        long lbfd=oc_openat(pkg_fd,"layout.bin",OC_READ,0);
        OcMeta lbm={0}; unsigned lb_len=0;
        if (lbfd<0 || oc_stat((int)lbfd,&lbm)<0 || (lbm.mode&OC_TYPE)!=OC_REGULAR || lbm.size>16384) ok=0;
        while (ok && lb_len<(unsigned)lbm.size) {
            long r=oc_read((int)lbfd,cm.io+lb_len,(unsigned)lbm.size-lb_len);
            if (r==-4) continue;
            if (r<=0) { ok=0; break; }
            lb_len+=(unsigned)r;
        }
        if (lbfd>=0 && oc_close((int)lbfd)<0) ok=0;
        char *ltxt=cm.io+16384;
        if (ok) ok=oc_text(pkg_fd,"layout.txt",ltxt,16384,0)>0;
        char *p=ltxt;
        while (ok && *p) {
            char *ln=p; while (*p && *p!='\n') ++p;
            if (*p=='\n') *p++=0;
            while (*ln==' '||*ln=='\t') ++ln;
            if (!*ln) { ok=0; break; }
            char *a=ln; while (*ln && *ln!=' ' && *ln!='\t') ++ln;
            if (!*ln) { ok=0; break; }
            *ln++=0;
            while (*ln==' '||*ln=='\t') ++ln;
            char *b=ln; while (*ln && *ln!=' ' && *ln!='\t') ++ln;
            while (*ln==' '||*ln=='\t') ++ln;
            if (*ln) { ok=0; break; }
            /* Trim trailing spaces from b. */
            char *be=b; while (*be && *be!=' ' && *be!='\t') ++be;
            *be=0;
            oc_u64 dst_off=0, src_off=0;
            if (!oc_decimal(a,&dst_off) || !oc_decimal(b,&src_off) ||
                src_off>(oc_u64)lb_len || (oc_u64)lb_len-src_off<4 ||
                dst_off>(oc_u64)out_total || (oc_u64)out_total-dst_off<4) { ok=0; break; }
            ok=oc_seek_set((int)ofd,(unsigned)dst_off)==(long)dst_off &&
                oc_write_all((int)ofd,cm.io+(unsigned)src_off,4);
        }
    }
    if (ok) ok=oc_mode((int)ofd,0600)>=0 && oc_sync((int)ofd)>=0;
    if (oc_close((int)ofd)<0) ok=0;
    return ok;
}

static int oc_compose_mmui(int pkg_fd, int orig_fd, int work_fd) {
    long sfd=oc_openat(orig_fd,"mmui.so",OC_READ,0);
    if (sfd<0) return 0;
    OcMeta sm={0};
    if (oc_stat((int)sfd,&sm)<0 || (sm.mode&OC_TYPE)!=OC_REGULAR || sm.size>33554432) {
        (void)oc_close((int)sfd); return 0;
    }
    long ofd=oc_openat(work_fd,"mmui.so",OC_RW|OC_CREATE|OC_EXCLUSIVE,0600);
    if (ofd<0) { (void)oc_close((int)sfd); return 0; }
    int ok=oc_copy_exact_bytes((int)sfd,(int)ofd,(unsigned)sm.size);
    if (oc_close((int)sfd)<0) ok=0;
    static const struct { const char *name; unsigned off; } patches[6]={
        {"mmui-path.bin",15812u},{"mmui-sizes.bin",68u},{"mmui-length.bin",7112u},
        {"mmui-count-pointer.bin",7368u},{"mmui-length.bin",10688u},{"mmui-pointer.bin",12540u}
    };
    for (unsigned i=0; ok && i<6; ++i)
        ok=oc_patch_blob_at((int)ofd,(unsigned)sm.size,pkg_fd,patches[i].name,patches[i].off,0);
    if (ok) ok=oc_mode((int)ofd,0600)>=0 && oc_sync((int)ofd)>=0;
    if (oc_close((int)ofd)<0) ok=0;
    return ok;
}

/* ---------- Streaming text transforms ---------- */
static int oc_replace_stream(int sfd, int dfd,
                             const char *old1, const char *new1,
                             const char *old2, const char *new2) {
    OcCStream st; st.fd=sfd; st.at=st.filled=st.total=0; st.limit=524288;
    int had_nl=0, r, ok=1;
    unsigned o1=oc_length(old1), n1=oc_length(new1), c1=0, c2=0;
    unsigned o2=old2?oc_length(old2):0, n2=new2?oc_length(new2):0;
    while (ok && (r=oc_cstream_line(&st,cm.line,sizeof cm.line,&had_nl))==1) {
        char *p=cm.line; unsigned at=0;
        while (*p) {
            if (oc_prefix(p,old1)) {
                if (at+n1+2>=sizeof cm.out) { ok=0; break; }
                for (unsigned i=0; i<n1; ++i) cm.out[at++]=new1[i];
                p+=o1; ++c1;
            } else if (old2 && oc_prefix(p,old2)) {
                if (at+n2+2>=sizeof cm.out) { ok=0; break; }
                for (unsigned i=0; i<n2; ++i) cm.out[at++]=new2[i];
                p+=o2; ++c2;
            } else {
                if (at+2>=sizeof cm.out) { ok=0; break; }
                cm.out[at++]=*p++;
            }
        }
        if (ok) {
            if (had_nl) cm.out[at++]='\n';
            ok=oc_write_all(dfd,cm.out,at);
        }
    }
    return ok && r==0 && c1==1 && (!old2 || c2==1);
}

static int oc_replace_file(int src_dir, const char *src_name, int dst_dir, const char *dst_name,
                           const char *old1, const char *new1, const char *old2, const char *new2) {
    long sfd=oc_openat(src_dir,src_name,OC_READ,0);
    if (sfd<0) return 0;
    long dfd=oc_openat(dst_dir,dst_name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (dfd<0) { (void)oc_close((int)sfd); return 0; }
    int ok=oc_replace_stream((int)sfd,(int)dfd,old1,new1,old2,new2) &&
        oc_mode((int)dfd,0600)>=0 && oc_sync((int)dfd)>=0;
    if (oc_close((int)sfd)<0) ok=0;
    if (oc_close((int)dfd)<0) ok=0;
    return ok;
}

static int oc_compose_index_tpl(int orig_fd, int work_fd) {
    long sfd=oc_openat(orig_fd,"index.html",OC_READ,0);
    if (sfd<0) return 0;
    long dfd=oc_openat(work_fd,"index-on.html",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (dfd<0) { (void)oc_close((int)sfd); return 0; }
    OcCStream st; st.fd=(int)sfd; st.at=st.filled=st.total=0; st.limit=524288;
    int in_comment=0, had_nl=0, r, ok=1;
    unsigned head_n=0, body_n=0;
    while (ok && (r=oc_cstream_line(&st,cm.line,sizeof cm.line,&had_nl))==1) {
        char *ln=cm.line;
        if (in_comment) {
            char *end=oc_cfind(ln,"-->");
            if (!end) continue;
            ln=end+3; in_comment=0;
        }
        for (;;) {
            char *start=oc_cfind(ln,"<!--");
            if (!start) break;
            char *end=oc_cfind(start+4,"-->");
            if (!end) { *start=0; in_comment=1; break; }
            char *tail=end+3;
            char *dst=start;
            while (*tail) *dst++=*tail++;
            *dst=0;
        }
        while (*ln==' '||*ln=='\t') ++ln;
        unsigned len=oc_length(ln);
        while (len && (ln[len-1]==' '||ln[len-1]=='\t')) ln[--len]=0;
        if (oc_prefix(ln,"<script ") || oc_prefix(ln,"<script\t")) {
            char *tp=oc_cfind(ln," type=\"text/javascript\"");
            if (tp) {
                char *tail=tp+23;
                while (*tail) *tp++=*tail++;
                *tp=0;
            }
        }
        if (oc_prefix(ln,"var baseApp = new BaseApp();")) ln[28]=0;
        if (!*ln) continue;
        if (oc_cfind(ln,"<head>")) {
            ++head_n;
            const char *hdr="\n<base href=\"file:///jci/gui/\" />\n"
                "<meta name=\"open-connect-token\" content=\"@TOKEN@\" data-boot=\"@BOOT@\" />\n"
                "<meta name=\"open-connect-version\" content=\"@VERSION@\" />\n"
                "<meta name=\"open-connect-notice\" content=\"@NOTICE@\" />\n";
            ok=oc_write_all((int)dfd,ln,oc_length(ln)) && oc_write_all((int)dfd,hdr,oc_length(hdr));
            continue;
        }
        if (oc_cfind(ln,"</body>")) {
            ++body_n;
            const char *inj="<script src=\"file:///tmp/open-connect/feature/runtime.js\"></script>\n";
            ok=oc_write_all((int)dfd,inj,oc_length(inj));
        }
        if (ok) ok=oc_write_all((int)dfd,ln,oc_length(ln)) && oc_write_all((int)dfd,"\n",1);
    }
    if (r!=0 || in_comment || head_n!=1 || body_n!=1) ok=0;
    if (ok) ok=oc_mode((int)dfd,0600)>=0 && oc_sync((int)dfd)>=0;
    if (oc_close((int)sfd)<0) ok=0;
    if (oc_close((int)dfd)<0) ok=0;
    if (ok) ok=oc_copy_file_at(work_fd,"index-on.html",work_fd,"index-off.html",0600,1,1,0);
    return ok;
}

static int oc_append_file_all(int src_dir, const char *name, int dst_fd, unsigned *bytes_out) {
    long fd=oc_openat(src_dir,name,OC_READ,0);
    if (fd<0) return 0;
    OcMeta m={0};
    int ok=oc_stat((int)fd,&m)>=0 && (m.mode&OC_TYPE)==OC_REGULAR && m.size>0 && m.size<=65536;
    unsigned tot=0;
    while (ok) {
        long r=oc_read((int)fd,cm.io,sizeof cm.io);
        if (r==-4) continue;
        if (r<0) { ok=0; break; }
        if (!r) break;
        if (!oc_write_all(dst_fd,cm.io,(unsigned)r)) { ok=0; break; }
        tot+=(unsigned)r;
    }
    if (oc_close((int)fd)<0) ok=0;
    if (ok) *bytes_out=tot;
    return ok && tot>0;
}

static int oc_compose_autostart(int pkg_fd, int orig_fd, int work_fd,
                                const char *root_path, const char *wleaf) {
    long sfd=oc_openat(orig_fd,"autostart",OC_READ,0);
    if (sfd<0) return 0;
    long dfd=oc_openat(work_fd,"autostart",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (dfd<0) { (void)oc_close((int)sfd); return 0; }
    OcCStream st; st.fd=(int)sfd; st.at=st.filled=st.total=0; st.limit=262144;
    int had_nl=0, r, ok=1, prev_sleep1=0;
    unsigned hook_n=0, join_n=0, hb=0, jb=0;
    while (ok && (r=oc_cstream_line(&st,cm.line,sizeof cm.line,&had_nl))==1) {
        if (prev_sleep1 && oc_equal(cm.line,"                $(/jci/scripts/get_board_type.sh)")) {
            if (hook_n!=1) { ok=0; break; }
            ok=oc_append_file_all(pkg_fd,"startup-join.sh",(int)dfd,&jb);
            ++join_n;
        }
        if (ok) ok=oc_write_all((int)dfd,cm.line,oc_length(cm.line)) && (!had_nl || oc_write_all((int)dfd,"\n",1));
        if (ok && oc_equal(cm.line,"        echo $MESSAGE_NORMALMODE")) {
            ok=oc_append_file_all(pkg_fd,"startup-hook.sh",(int)dfd,&hb);
            ++hook_n;
        }
        prev_sleep1=oc_equal(cm.line,"                sleep 1");
    }
    if (r!=0 || hook_n!=1 || join_n!=1 || !hb || !jb) ok=0;
    if (ok) ok=oc_mode((int)dfd,0600)>=0 && oc_sync((int)dfd)>=0;
    if (oc_close((int)sfd)<0) ok=0;
    if (oc_close((int)dfd)<0) ok=0;
    if (!ok) return 0;
    char dbase[320], apath[448];
    if (!oc_data_base(root_path,dbase,sizeof dbase) ||
        !oc_join4(apath,sizeof apath,dbase,"/composed/",wleaf,"/autostart")) return 0;
    char *argv[]={"sh","-n",apath,0};
    return oc_run_cmd("/bin/sh",argv,-1,0,0,-1)==0;
}

int oc_compose_pkg(int root, int data_fd, const char *root_path, const char *pkg_id,
                   const char **err_out) {
    if (!oc_hex(pkg_id,64) || !oc_originals_verify(data_fd)) return cerr(err_out,"compose_inputs_invalid");
    int pdir=oc_open_sub(data_fd,"packages",pkg_id);
    OcManifest pmf;
    if (pdir<0 || !oc_verify_dir_manifest(pdir,&pmf,cm.mf,sizeof cm.mf)) {
        if (pdir>=0) (void)oc_close(pdir);
        return cerr(err_out,"compose_inputs_invalid");
    }
    int comp_root=oc_open_private(data_fd,"composed");
    if (comp_root<0) { (void)oc_close(pdir); return cerr(err_out,"compose_create_failed"); }
    if (!oc_absent_at(comp_root,pkg_id)) {
        int existing=oc_open_private(comp_root,pkg_id);
        OcManifest emf;
        int eok=existing>=0 && oc_verify_dir_manifest(existing,&emf,cm.mf,sizeof cm.mf);
        if (existing>=0) (void)oc_close(existing);
        (void)oc_close(comp_root); (void)oc_close(pdir);
        return eok ? 1 : cerr(err_out,"composed_files_changed");
    }
    char nonce[33], wleaf[48];
    if (!oc_random(root,nonce) || !oc_join(wleaf,sizeof wleaf,".new-",nonce) ||
        oc_mkdir(comp_root,wleaf,0700)<0) {
        (void)oc_close(comp_root); (void)oc_close(pdir); return cerr(err_out,"compose_create_failed");
    }
    int wfd=oc_open_private(comp_root,wleaf);
    int orig=oc_open_private(data_fd,"originals");
    const char *ferr=0;
    if (wfd<0 || orig<0) { ferr="compose_create_failed"; goto out; }

    if (!oc_compose_uia(pdir,orig,wfd)) { ferr="compose_patch_failed"; goto out; }
    if (!oc_compose_mmui(pdir,orig,wfd)) { ferr="compose_patch_failed"; goto out; }

    /* VUI: verify stock svcjcivui.so + vui_config.xml, patch vui.so, rewrite vui.xml */
    {
        long vdir=oc_beneath(root,"jci/vui",OC_DIRECTORY,0);
        const char *vso_pin=oc_pin_digest(oc_base_pins[3].key,oc_base_pins[3].digest);
        const char *vxml_pin=oc_pin_digest(oc_base_pins[4].key,oc_base_pins[4].digest);
        if (vdir<0 || !oc_verify_file_sha((int)vdir,"svcjcivui.so",vso_pin,33554432) ||
            !oc_verify_file_sha((int)vdir,"vui_config.xml",vxml_pin,262144)) {
            if (vdir>=0) (void)oc_close((int)vdir);
            ferr="vui_inputs_changed"; goto out;
        }
        long vsfd=oc_openat((int)vdir,"svcjcivui.so",OC_READ,0);
        OcMeta vsm={0};
        long vdfd=vsfd>=0 ? oc_openat(wfd,"vui.so",OC_RW|OC_CREATE|OC_EXCLUSIVE,0600) : -1;
        int vok=vsfd>=0 && vdfd>=0 && oc_stat((int)vsfd,&vsm)>=0 && (vsm.mode&OC_TYPE)==OC_REGULAR &&
            vsm.size<=33554432 && oc_copy_exact_bytes((int)vsfd,(int)vdfd,(unsigned)vsm.size) &&
            oc_patch_blob_at((int)vdfd,(unsigned)vsm.size,pdir,"vui-path.bin",68196u,24u) &&
            oc_mode((int)vdfd,0600)>=0 && oc_sync((int)vdfd)>=0;
        if (vsfd>=0 && oc_close((int)vsfd)<0) vok=0;
        if (vdfd>=0 && oc_close((int)vdfd)<0) vok=0;
        if (vok) {
            const char *vout_pin=oc_pin_digest("composed/vui.so",
                "6cc31cd92167624093f95924a15a27536aec2e40cecc170b47cce72d703ba18f");
            vok=oc_verify_file_sha(wfd,"vui.so",vout_pin,33554432);
        }
        if (!vok) { (void)oc_close((int)vdir); ferr="compose_patch_failed"; goto out; }
        vok=oc_replace_file((int)vdir,"vui_config.xml",wfd,"vui.xml",
            "value=\"/jci/vui/plugins\"","value=\"/tmp/open-connect/vui-plugins/\"",0,0);
        (void)oc_close((int)vdir);
        if (!vok) { ferr="compose_xml_failed"; goto out; }
    }

    if (!oc_replace_file(orig,"mmui.xml",wfd,"mmui.xml",
        "name=\"system\" libpath=\"/jci/mmui/uia/\" lib=\"libjciuiasystem.so\"",
        "name=\"system\" libpath=\"/tmp/open-connect/feature/\" lib=\"uia.so\"",0,0)) {
        ferr="compose_xml_failed"; goto out;
    }
    if (!oc_compose_index_tpl(orig,wfd)) { ferr="compose_index_failed"; goto out; }
    if (!oc_replace_file(orig,"sm.conf",wfd,"sm-normal-off.conf",
        "args=\"-u /jci/gui/index.html\"","args=\"-u /tmp/open-connect/feature/index.html\"",0,0) ||
        !oc_replace_file(orig,"sm.conf",wfd,"sm-normal-on.conf",
        "args=\"-u /jci/gui/index.html\"","args=\"-u /tmp/open-connect/feature/index.html\"",
        "name=\"jciMMUI\" path=\"/jci/mmui/svcjcimmui.so\"","name=\"jciMMUI\" path=\"/tmp/open-connect/feature/mmui.so\"") ||
        !oc_replace_file(orig,"sm_WCP.conf",wfd,"sm-wcp-off.conf",
        "args=\"-u /jci/gui/index.html\"","args=\"-u /tmp/open-connect/feature/index.html\"",0,0) ||
        !oc_replace_file(orig,"sm_WCP.conf",wfd,"sm-wcp-on.conf",
        "args=\"-u /jci/gui/index.html\"","args=\"-u /tmp/open-connect/feature/index.html\"",
        "name=\"jciMMUI\" path=\"/jci/mmui/svcjcimmui.so\"","name=\"jciMMUI\" path=\"/tmp/open-connect/feature/mmui.so\"")) {
        ferr="compose_config_failed"; goto out;
    }
    if (!oc_compose_autostart(pdir,orig,wfd,root_path,wleaf)) { ferr="startup_anchor_missing"; goto out; }

    /* Write files.sha256 for all 12 composed members in exact oc_composed_names order. */
    {
        long mfd=oc_openat(wfd,"files.sha256",OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        int mok=mfd>=0;
        for (unsigned i=0; mok && i<12; ++i) {
            char dig[65], row[160]; OcMeta mm={0};
            mok=oc_hash_file_at(wfd,oc_composed_names[i],dig,&mm) &&
                oc_join4(row,sizeof row,dig,"  ",oc_composed_names[i],"\n") &&
                oc_write_all((int)mfd,row,oc_length(row));
        }
        if (mok) mok=oc_mode((int)mfd,0600)>=0 && oc_sync((int)mfd)>=0;
        if (mfd>=0 && oc_close((int)mfd)<0) mok=0;
        if (!mok) { ferr="compose_manifest_failed"; goto out; }
    }
    if (oc_sync(wfd)<0) { ferr="compose_publish_failed"; goto out; }
    (void)oc_close(wfd); wfd=-1;
    if (oc_rename(comp_root,wleaf,pkg_id)<0 || oc_sync(comp_root)<0) ferr="compose_publish_failed";

out:
    if (orig>=0) (void)oc_close(orig);
    if (wfd>=0) (void)oc_close(wfd);
    if (ferr) oc_rm_subdir(comp_root,wleaf);
    (void)oc_close(comp_root);
    (void)oc_close(pdir);
    return ferr ? cerr(err_out,ferr) : 1;
}

/* ---------- Dependencies capture & access/selector capture ---------- */
typedef struct { unsigned count; int ok; } OcNameList;
static int oc_collect_visible_cb(const char *name, void *raw) {
    OcNameList *nl=raw;
    if (name[0]=='.') return 1;
    if (!oc_key(name) || nl->count>=80 || !oc_join(cm.names[nl->count],64,"",name)) { nl->ok=0; return 0; }
    ++nl->count;
    return 1;
}

static int oc_deps_append_dir(int dir_fd, const char *scope_prefix, const char *pkg_id, int out_fd) {
    OcNameList nl={0,1};
    if (!oc_dir_iter(dir_fd,oc_collect_visible_cb,&nl) || !nl.ok || !nl.count) return 0;
    for (unsigned i=1; i<nl.count; ++i) {
        char tmp[64]; (void)oc_join(tmp,64,"",cm.names[i]);
        unsigned j=i;
        while (j>0 && oc_cstr_cmp(cm.names[j-1],tmp)>0) {
            (void)oc_join(cm.names[j],64,"",cm.names[j-1]);
            --j;
        }
        (void)oc_join(cm.names[j],64,"",tmp);
    }
    for (unsigned i=0; i<nl.count; ++i) {
        char dig[65], row[256]; OcMeta m={0};
        if (!oc_hash_file_at(dir_fd,cm.names[i],dig,&m) ||
            !oc_join4(row,sizeof row,dig,"  ",scope_prefix,pkg_id) ||
            !oc_join4(row,sizeof row,row,"/",cm.names[i],"\n") ||
            !oc_write_all(out_fd,row,oc_length(row))) return 0;
    }
    return 1;
}

static int oc_dependencies_capture_to(int root, int data_fd, const char *pkg_id, int dst_dir) {
    long ofd=oc_openat(dst_dir,"dependencies",OC_WRITE|OC_CREATE|OC_TRUNC,0600);
    if (ofd<0) return 0;
    int ok=1;
    for (unsigned i=0; ok && i<19; ++i) {
        char dig[65], row[160]; OcMeta m={0};
        long fd=oc_beneath(root,oc_root_paths[i]+1,OC_READ,0);
        ok=fd>=0 && oc_hash_copy((int)fd,-1,33554432,dig,&m)==OC_COPY_OK &&
            oc_join4(row,sizeof row,dig,"  root/",oc_root_names[i],"\n") &&
            oc_write_all((int)ofd,row,oc_length(row));
        if (fd>=0 && oc_close((int)fd)<0) ok=0;
    }
    if (ok && !oc_equal(pkg_id,"-")) {
        int pdir=oc_open_sub(data_fd,"packages",pkg_id);
        int cdir=ok ? oc_open_sub(data_fd,"composed",pkg_id) : -1;
        ok=pdir>=0 && cdir>=0 &&
            oc_deps_append_dir(pdir,"package-",pkg_id,(int)ofd) &&
            oc_deps_append_dir(cdir,"composed-",pkg_id,(int)ofd);
        if (cdir>=0) (void)oc_close(cdir);
        if (pdir>=0) (void)oc_close(pdir);
    }
    if (ok) ok=oc_mode((int)ofd,0600)>=0 && oc_sync((int)ofd)>=0;
    if (oc_close((int)ofd)<0) ok=0;
    return ok;
}

static int oc_access_capture(int root, int dst_fd, const char *uart, const char *ssh,
                             const char *key, const char *login_inode_opt) {
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    long essh=oc_beneath(root,"etc/ssh",OC_DIRECTORY,0);
    if (ubin<0 || essh<0) {
        if (ubin>=0) (void)oc_close((int)ubin);
        if (essh>=0) (void)oc_close((int)essh);
        return 0;
    }
    OcMeta lm={0}, sm={0}; char lms[40], sms[40], ino_s[24], line[320];
    int ok=oc_metadata((int)ubin,"runlogin",&lm)>=0 && (lm.mode&OC_TYPE)==OC_REGULAR &&
        oc_metadata((int)essh,"sshd_config",&sm)>=0 && (sm.mode&OC_TYPE)==OC_REGULAR &&
        oc_meta_mode_str(&lm,lms) && oc_meta_mode_str(&sm,sms) &&
        oc_copy_file_at((int)ubin,"runlogin",dst_fd,"runlogin",0600,1,1,0) &&
        oc_copy_file_at((int)essh,"sshd_config",dst_fd,"sshd.conf",0600,1,1,0);
    (void)oc_close((int)ubin); (void)oc_close((int)essh);
    if (!ok) return 0;
    const char *ino_str=login_inode_opt;
    if (!ino_str || !*ino_str || oc_equal(ino_str,"-")) {
        oc_u64_dec(lm.inode,ino_s);
        ino_str=ino_s;
    }
    return oc_join4(line,sizeof line,uart,"|",ssh,"|") &&
        oc_join4(line,sizeof line,line,key,"|",lms) &&
        oc_join4(line,sizeof line,line,"|",sms,"|") &&
        oc_join4(line,sizeof line,line,ino_str,"\n",0) &&
        oc_new_text(dst_fd,"access",line,0600);
}

static int oc_selector_capture(int root, const char *sel_hash, const char *sel_meta,
                               const char *sel_pkg, int dst_fd) {
    if (!oc_selector_matches_at(root,sel_hash,sel_meta)) return 0;
    char line[256];
    if (oc_equal(sel_hash,"-")) return oc_new_text(dst_fd,"selector","-\n",0600);
    return oc_join4(line,sizeof line,sel_hash,"|",sel_meta,"|") &&
        oc_join4(line,sizeof line,line,sel_pkg,"\n",0) &&
        oc_new_text(dst_fd,"selector",line,0600);
}

static int oc_selector_compose(int data_fd, const char *pkg_id, long owner, long group, int dst_fd) {
    int pdir=oc_open_sub(data_fd,"packages",pkg_id);
    if (pdir<0) return 0;
    OcManifest pmf;
    int ok=oc_verified_text(pdir,"files.sha256",pkg_id,cm.mf,sizeof cm.mf) && oc_manifest(cm.mf,&pmf,0);
    const char *bd=ok?oc_digest(&pmf,"boot-select"):0;
    ok=ok && bd && oc_verify_file_sha(pdir,"boot-select",bd,33554432);
    (void)oc_close(pdir);
    if (!ok) return 0;
    char os[24], gs[24], line[256];
    oc_u64_dec((oc_u64)owner,os); oc_u64_dec((oc_u64)group,gs);
    return oc_join4(line,sizeof line,bd,"|700:",os,":") &&
        oc_join4(line,sizeof line,line,gs,"|",pkg_id) &&
        oc_join(line,sizeof line,line,"\n") &&
        oc_new_text(dst_fd,"selector",line,0600);
}

static int oc_stock_runlogin_ok(int root, const char **err_out) {
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    if (ubin<0) return cerr(err_out,"unsupported_console");
    char dig[65], ino_s[24], hleaf[64]; OcMeta lm={0};
    const char *pin=oc_pin_digest("root/runlogin",
        "b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8");
    int ok=oc_hash_file_at((int)ubin,"runlogin",dig,&lm) && oc_equal(dig,pin);
    if (!ok) { (void)oc_close((int)ubin); return cerr(err_out,"unsupported_console"); }
    oc_u64_dec(lm.inode,ino_s);
    int absent_ok=oc_join(hleaf,sizeof hleaf,".open-connect-runlogin-",ino_s) && oc_absent_at((int)ubin,hleaf);
    (void)oc_close((int)ubin);
    return absent_ok ? 1 : cerr(err_out,"console_hold_conflict");
}

static int oc_state_capture(int root, const char *root_path, int data_fd,
                            const char *pkg_id, int awfd, const char *prefs_text,
                            const char *session_dir, long owner, long group,
                            char out_id[65]) {
    long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
    if (ubin<0) return 0;
    OcMeta am={0}; char ams[40], nv[16];
    int ok=oc_metadata((int)ubin,"autostart",&am)>=0 && (am.mode&OC_TYPE)==OC_REGULAR &&
        oc_meta_mode_str(&am,ams) && oc_nvram_at(root,nv) &&
        oc_copy_file_at((int)ubin,"autostart",awfd,"autostart",0600,1,1,0);
    (void)oc_close((int)ubin);
    if (!ok || !oc_dependencies_capture_to(root,data_fd,pkg_id,awfd)) return 0;
    return oc_snapshot_create(root,data_fd,0,pkg_id,nv,ams,0,awfd,prefs_text,
                              session_dir,root_path,owner,group,out_id);
}

static int oc_access_snapshot(int root, const char *root_path, int data_fd,
                              const char *snap_id, int awfd, const char *session_dir,
                              long owner, long group, char out_id[65]) {
    OcTxnSnap *s=&oc_snap_pool[2];
    if (!oc_txn_read_snap(data_fd,snap_id,s)) return 0;
    return oc_snapshot_create(root,data_fd,snap_id,s->pkg,s->nvram,s->meta,snap_id,
                              awfd,"",session_dir,root_path,owner,group,out_id);
}

static int oc_ensure_subdir(int dir, const char *name) {
    if (oc_absent_at(dir,name) && oc_mkdir(dir,name,0700)<0) return 0;
    int sub=oc_open_private(dir,name);
    if (sub<0) return 0;
    (void)oc_close(sub);
    return 1;
}

static int oc_build_install_prefs(int data_fd, const char *pkg_id, const char *nvram,
                                  const char *meta, const char *old_cfg_text,
                                  char out_cfg[1024], OcPrefs *out_prefs) {
    OcManifest pmf; OcCatalog cat; cat.count=0;
    int pdir=oc_open_pkg_verified(data_fd,pkg_id,cm.mf,sizeof cm.mf,&pmf);
    if (pdir<0) return 0;
    const char *sd=oc_digest(&pmf,"services.tsv");
    int ok=sd && oc_verified_text(pdir,"services.tsv",sd,cm.cat,sizeof cm.cat) &&
        oc_catalog_load(cm.cat,oc_length(cm.cat),&cat);
    (void)oc_close(pdir);
    if (!ok) return 0;

    static char parse_buf[1024];
    if (old_cfg_text && *old_cfg_text) {
        OcPrefs old_p;
        if (!oc_join(parse_buf,sizeof parse_buf,"",old_cfg_text) ||
            !oc_prefs_parse(parse_buf,0,1,&old_p)) return 0;
        /* Every prior service must exist in the new catalog or be the retired "dvd" service. */
        for (unsigned j=0; j<old_p.svc_count; ++j) {
            int known=oc_equal(old_p.svc_ids[j],"dvd");
            for (unsigned i=0; !known && i<cat.count; ++i)
                if (oc_equal(old_p.svc_ids[j],cat.rows[i].id)) known=1;
            if (!known) return 0;
        }
        *out_prefs=old_p;
        out_prefs->package=(char *)pkg_id;
        out_prefs->nvram=(char *)nvram;
        out_prefs->metadata=(char *)meta;
        if (!out_prefs->has_autoshow) { out_prefs->autoshow="0"; out_prefs->has_autoshow=1; }
        out_prefs->svc_count=cat.count;
        for (unsigned i=0; i<cat.count; ++i) {
            char *val=cat.rows[i].def;
            for (unsigned j=0; j<old_p.svc_count; ++j)
                if (oc_equal(old_p.svc_ids[j],cat.rows[i].id)) { val=old_p.svc_vals[j]; break; }
            out_prefs->svc_ids[i]=cat.rows[i].id;
            out_prefs->svc_vals[i]=val;
            if (oc_equal(cat.rows[i].id,"pandora")) out_prefs->pandora=val;
        }
    } else {
        out_prefs->is_oc2=1;
        out_prefs->package=(char *)pkg_id;
        out_prefs->nvram=(char *)nvram;
        out_prefs->metadata=(char *)meta;
        out_prefs->touch="1"; out_prefs->warning="1"; out_prefs->base="0";
        out_prefs->wireless="0"; out_prefs->autoshow="0"; out_prefs->has_autoshow=1;
        out_prefs->pandora="1"; out_prefs->svc_count=cat.count;
        for (unsigned i=0; i<cat.count; ++i) {
            out_prefs->svc_ids[i]=cat.rows[i].id;
            out_prefs->svc_vals[i]=cat.rows[i].def;
            if (oc_equal(cat.rows[i].id,"pandora")) out_prefs->pandora=cat.rows[i].def;
        }
    }
    return oc_prefs_write(&cat,out_prefs,out_cfg,1024);
}

/* ---------- Full transactional install/upgrade/reinstall ---------- */
int oc_install_run(int root, const char *root_path, const char *session_dir,
                   long owner, long group, const char **err_out) {
    /* 1. Verify maintenance bundle manifest + root ro,noatime. */
    {
        long sdir=oc_openat(OC_CWD,session_dir,OC_DIRECTORY,0);
        OcManifest smf;
        int sok=sdir>=0 && oc_verify_dir_manifest((int)sdir,&smf,cm.mf,sizeof cm.mf);
        if (sdir>=0) (void)oc_close((int)sdir);
        if (!sok) return cerr(err_out,"incomplete_maintenance_bundle");
    }
    if (!oc_mounts_mode(root,oc_mscratch,sizeof oc_mscratch,0)) return cerr(err_out,"root_mount_changed");

    int exists=0, data_fd=-1;
    char rec_buf[1024], *rec[13]={0};
    if (!oc_data_absent(root)) {
        data_fd=oc_open_data_dir(root);
        if (data_fd<0) return cerr(err_out,"invalid_state_directory");
        if (!oc_absent_at(data_fd,"record")) {
            if (!oc_record_read_any(data_fd,owner,group,rec_buf,sizeof rec_buf,rec)) {
                (void)oc_close(data_fd); return cerr(err_out,"invalid_record");
            }
            if (!(oc_equal(rec[6],"-") && oc_equal(rec[7],"-") &&
                  (oc_equal(rec[1],"active") || oc_equal(rec[1],"removed")))) {
                (void)oc_close(data_fd); return cerr(err_out,"operation_pending");
            }
            exists=1;
        } else {
            (void)oc_close(data_fd); return cerr(err_out,"invalid_record");
        }
    }

    if (exists) {
        if (!oc_targets_match(root,data_fd,rec[5],rec[4],owner,group) ||
            !oc_dependencies_match(root,data_fd,rec[5],owner,group)) {
            (void)oc_close(data_fd); return cerr(err_out,"state_changed");
        }
        if (oc_equal(rec[1],"removed")) {
            int rok=oc_originals_verify(data_fd) &&
                (oc_equal(rec[4],rec[5]) ||
                 (oc_targets_match(root,data_fd,rec[4],rec[4],owner,group) &&
                  oc_dependencies_match(root,data_fd,rec[4],owner,group)));
            if (!rok) { (void)oc_close(data_fd); return cerr(err_out,"originals_changed"); }
        }
    }

    if (!oc_stock_dependencies_ok(root)) {
        if (data_fd>=0) (void)oc_close(data_fd);
        return cerr(err_out,"unsupported_original");
    }

    /* 2. initial_begin: stage fresh state in hidden sibling directory until initial_publish. */
    int parent_fd=-1;
    char dbase[320], parent_abs[320], dleaf[128], init_leaf[64];
    init_leaf[0]=0;
    if (!oc_data_base(root_path,dbase,sizeof dbase)) {
        if (data_fd>=0) (void)oc_close(data_fd);
        return cerr(err_out,"state_create_failed");
    }
    unsigned dlen=oc_length(dbase), sl=0;
    for (unsigned i=0; i<dlen; ++i) if (dbase[i]=='/') sl=i;
    if (!sl || sl+1>=dlen || dlen-sl-1>=sizeof dleaf) {
        if (data_fd>=0) (void)oc_close(data_fd);
        return cerr(err_out,"state_create_failed");
    }
    for (unsigned i=0; i<sl; ++i) parent_abs[i]=dbase[i];
    parent_abs[sl]=0;
    (void)oc_join(dleaf,sizeof dleaf,"",dbase+sl+1);
    parent_fd=(int)oc_openat(OC_CWD,parent_abs,OC_DIRECTORY,0);
    if (parent_fd<0) {
        if (data_fd>=0) (void)oc_close(data_fd);
        return cerr(err_out,"state_create_failed");
    }

    const char *ferr=0;
    char aw_leaf[48]; aw_leaf[0]=0;
    int awfd=-1;
    if (!exists) {
        char inonce[33];
        if (!oc_absent_at(parent_fd,dleaf)) { ferr="invalid_record"; goto fail; }
        if (!oc_random(root,inonce) || !oc_join(init_leaf,sizeof init_leaf,".open-connect-initial-",inonce) ||
            oc_mkdir(parent_fd,init_leaf,0700)<0) { init_leaf[0]=0; ferr="state_create_failed"; goto fail; }
        data_fd=oc_open_private(parent_fd,init_leaf);
        if (data_fd<0) { ferr="state_create_failed"; goto fail; }
    }
    if (!oc_ensure_subdir(data_fd,"snapshots") || !oc_ensure_subdir(data_fd,"packages") ||
        !oc_ensure_subdir(data_fd,"composed") || !oc_ensure_subdir(data_fd,"keys") ||
        oc_sync(data_fd)<0) { ferr="state_create_failed"; goto fail; }

    /* 3. originals_save */
    if (!oc_originals_save(root,data_fd,&ferr)) goto fail;

    /* 4. Capture current access, selector, before snapshot, and base snapshot. */
    char old_pkg[65], old_cfg[1024], uart[4], ssh[4], key[65], before_id[65], base_id[65];
    (void)oc_join(old_pkg,sizeof old_pkg,"","-");
    old_cfg[0]=0; (void)oc_join(uart,4,"","0"); (void)oc_join(ssh,4,"","0"); (void)oc_join(key,65,"","-");
    before_id[0]=0; base_id[0]=0;
    if (exists) (void)oc_join(base_id,sizeof base_id,"",rec[4]);

    {
        char anonce[33];
        if (!oc_random(root,anonce) || !oc_join(aw_leaf,sizeof aw_leaf,".access-",anonce) ||
            oc_mkdir(data_fd,aw_leaf,0700)<0) { aw_leaf[0]=0; ferr="access_plan_failed"; goto fail; }
        awfd=oc_open_private(data_fd,aw_leaf);
        if (awfd<0) { ferr="access_plan_failed"; goto fail; }
    }

    if (exists && oc_equal(rec[1],"active")) {
        OcTxnSnap *cur=&oc_snap_pool[0];
        if (!oc_txn_read_snap(data_fd,rec[5],cur)) { ferr="invalid_snapshot"; goto fail; }
        if (!cur->is_oc2) { ferr="unsupported_snapshot"; goto fail; }
        int cdir=oc_open_sub(data_fd,"snapshots",rec[5]);
        int cok=cdir>=0 && oc_text(cdir,"config",old_cfg,sizeof old_cfg,0)>0;
        if (cdir>=0) (void)oc_close(cdir);
        if (!cok) { ferr="invalid_snapshot"; goto fail; }
        (void)oc_join(old_pkg,sizeof old_pkg,"",cur->pkg);
        if (cur->has_access) {
            if (oc_equal(cur->acc_f[5],"-")) { ferr="developer_reinstall_required"; goto fail; }
            (void)oc_join(uart,4,"",cur->acc_f[0]);
            (void)oc_join(ssh,4,"",cur->acc_f[1]);
            (void)oc_join(key,65,"",cur->acc_f[2]);
        } else if (!oc_stock_runlogin_ok(root,&ferr)) goto fail;
        if (!oc_access_capture(root,awfd,uart,ssh,key,cur->has_access?cur->acc_f[5]:0)) {
            ferr="access_backup_failed"; goto fail;
        }
        if (!oc_selector_capture(root,cur->sel_hash,cur->sel_meta,cur->sel_pkg,awfd)) {
            ferr="selector_backup_failed"; goto fail;
        }
        /* Also carry forward current rendered profiles so before snapshot is self-contained. */
        int cdir2=oc_open_sub(data_fd,"snapshots",rec[5]);
        int pcok=cdir2>=0 && oc_copy_opt(cdir2,awfd,0x1f0,0);
        if (cdir2>=0) (void)oc_close(cdir2);
        if (!pcok || !oc_state_capture(root,root_path,data_fd,old_pkg,awfd,old_cfg,session_dir,owner,group,before_id)) {
            ferr="checkpoint_failed"; goto fail;
        }
        /* Check active base=1 / touch=2 pins before mutating packages. */
        if (oc_equal(cur->base,"1") || oc_equal(cur->touch,"2")) {
            if (!oc_check_active_pins(root,data_fd,old_pkg,rec[5],cur->base,cur->touch,&ferr)) goto fail;
        }
    } else {
        /* Stock autostart + stock runlogin verification. */
        {
            long ubin=oc_beneath(root,"usr/bin",OC_DIRECTORY,0);
            char adig[65], odig[65]; OcMeta am={0}, om={0};
            int orig=oc_open_private(data_fd,"originals");
            int sok=ubin>=0 && orig>=0 &&
                oc_hash_file_at((int)ubin,"autostart",adig,&am) &&
                oc_hash_file_at(orig,"autostart",odig,&om) && oc_equal(adig,odig);
            if (ubin>=0) (void)oc_close((int)ubin);
            if (orig>=0) (void)oc_close(orig);
            if (!sok) { ferr="unsupported_startup"; goto fail; }
        }
        if (!oc_stock_runlogin_ok(root,&ferr)) goto fail;
        if (!oc_access_capture(root,awfd,"0","0","-",0)) { ferr="access_backup_failed"; goto fail; }
        if (!oc_selector_capture(root,"-","-","-",awfd)) { ferr="selector_backup_failed"; goto fail; }
        if (exists) {
            (void)oc_join(before_id,sizeof before_id,"",rec[5]);
            OcTxnSnap *cur=&oc_snap_pool[0];
            if (!oc_txn_read_snap(data_fd,before_id,cur)) { ferr="invalid_snapshot"; goto fail; }
            if (!cur->has_access) {
                char upgraded[65];
                if (!oc_access_snapshot(root,root_path,data_fd,before_id,awfd,session_dir,owner,group,upgraded)) {
                    ferr="checkpoint_failed"; goto fail;
                }
                (void)oc_join(before_id,sizeof before_id,"",upgraded);
            }
        } else {
            if (!oc_state_capture(root,root_path,data_fd,"-",awfd,"",session_dir,owner,group,before_id)) {
                ferr="checkpoint_failed"; goto fail;
            }
            (void)oc_join(base_id,sizeof base_id,"",before_id);
        }
    }

    if (exists) {
        OcTxnSnap *bs=&oc_snap_pool[0];
        if (!oc_txn_read_snap(data_fd,base_id,bs)) { ferr="originals_changed"; goto fail; }
        if (!bs->has_access) {
            char upgraded[65];
            if (!oc_access_snapshot(root,root_path,data_fd,base_id,awfd,session_dir,owner,group,upgraded)) {
                ferr="access_backup_failed"; goto fail;
            }
            (void)oc_join(base_id,sizeof base_id,"",upgraded);
        }
    }

    /* 5. Save package from verified RAM session. */
    char pkg_id[65];
    if (!oc_package_save(root,data_fd,session_dir,pkg_id,&ferr)) goto fail;

    /* 6. initial_publish: atomically publish fresh state directory with settled removed record. */
    char *work_rec[13];
    char rev_init[33];
    if (!exists) {
        work_rec[0]="OC1"; work_rec[1]="removed"; work_rec[2]=rev_init; work_rec[3]=pkg_id;
        work_rec[4]=base_id; work_rec[5]=before_id; work_rec[6]="-"; work_rec[7]="-";
        work_rec[8]="-"; work_rec[9]="0"; work_rec[10]="-"; work_rec[11]="-"; work_rec[12]="-";
        if (!oc_record_write_atomic(root,data_fd,work_rec,rev_init)) { ferr="record_rename_failed"; goto fail; }
        work_rec[2]=rev_init;
        if (!oc_absent_at(parent_fd,dleaf)) { ferr="state_create_failed"; goto fail; }
        (void)oc_close(awfd); awfd=-1;
        (void)oc_close(data_fd); data_fd=-1;
        if (oc_rename(parent_fd,init_leaf,dleaf)<0 || oc_sync(parent_fd)<0) {
            ferr="state_publish_failed"; goto fail;
        }
        init_leaf[0]=0; exists=1;
        data_fd=oc_open_data_dir(root);
        awfd=data_fd>=0 ? oc_open_private(data_fd,aw_leaf) : -1;
        if (data_fd<0 || awfd<0) { ferr="state_publish_failed"; goto fail; }
    } else {
        for (unsigned i=0; i<13; ++i) work_rec[i]=rec[i];
        work_rec[3]=pkg_id; work_rec[4]=base_id;
        if (oc_equal(rec[1],"removed")) (void)oc_sync(parent_fd);
    }

    /* 7. Compose firmware artifacts for pkg_id. */
    if (!oc_compose_pkg(root,data_fd,root_path,pkg_id,&ferr)) goto fail;

    /* 8. Compose new access, selector, preferences, rendered profiles, and dependencies into fresh staging dir. */
    (void)oc_close(awfd); awfd=-1;
    oc_rm_subdir(data_fd,aw_leaf); aw_leaf[0]=0;
    {
        char anonce[33];
        if (!oc_random(root,anonce) || !oc_join(aw_leaf,sizeof aw_leaf,".access-",anonce) ||
            oc_mkdir(data_fd,aw_leaf,0700)<0) { aw_leaf[0]=0; ferr="access_plan_failed"; goto fail; }
        awfd=oc_open_private(data_fd,aw_leaf);
        if (awfd<0) { ferr="access_plan_failed"; goto fail; }
    }

    char console_dig[65]; console_dig[0]=0;
    {
        OcManifest pmf;
        int pdir=oc_open_pkg_verified(data_fd,pkg_id,cm.mf,sizeof cm.mf,&pmf);
        const char *cd=pdir>=0?oc_digest(&pmf,"console.sh"):0;
        int cok=pdir>=0 && cd && oc_join(console_dig,sizeof console_dig,"",cd);
        if (pdir>=0) (void)oc_close(pdir);
        if (!cok) { ferr="access_plan_failed"; goto fail; }
    }
    if (!oc_access_compose(root,root_path,data_fd,session_dir,base_id,console_dig,
                           awfd,aw_leaf,uart,ssh,key,owner,group)) {
        ferr="access_plan_failed"; goto fail;
    }
    if (!oc_selector_compose(data_fd,pkg_id,owner,group,awfd)) { ferr="selector_plan_failed"; goto fail; }

    OcTxnSnap *bs=&oc_snap_pool[0];
    if (!oc_txn_read_snap(data_fd,base_id,bs)) { ferr="originals_changed"; goto fail; }
    char new_cfg[1024]; OcPrefs new_prefs;
    const char *want_nvram=bs->nvram;
    if (!oc_build_install_prefs(data_fd,pkg_id,want_nvram,bs->meta,old_cfg,new_cfg,&new_prefs)) {
        ferr="plan_failed"; goto fail;
    }
    if (!old_cfg[0] || oc_equal(new_prefs.touch,"1")) {
        want_nvram="disable";
        if (!oc_build_install_prefs(data_fd,pkg_id,want_nvram,bs->meta,old_cfg,new_cfg,&new_prefs)) {
            ferr="plan_failed"; goto fail;
        }
    }

    char cfg_abs[400];
    if (!oc_new_text(awfd,"config",new_cfg,0600) ||
        !oc_join4(cfg_abs,sizeof cfg_abs,dbase,"/",aw_leaf,"/config") ||
        !oc_render_all_profiles(data_fd,root_path,pkg_id,cfg_abs,oc_length(new_cfg),&new_prefs,awfd)) {
        ferr="plan_failed"; goto fail;
    }
    if (!oc_dependencies_capture_to(root,data_fd,pkg_id,awfd)) {
        ferr="checkpoint_dependencies_failed"; goto fail;
    }
    {
        int cdir=oc_open_sub(data_fd,"composed",pkg_id);
        int aok=cdir>=0 && oc_copy_file_at(cdir,"autostart",awfd,"autostart",0600,1,1,0);
        if (cdir>=0) (void)oc_close(cdir);
        if (!aok) { ferr="plan_failed"; goto fail; }
    }

    char after_id[65];
    if (!oc_snapshot_create(root,data_fd,0,pkg_id,want_nvram,bs->meta,0,awfd,new_cfg,
                            session_dir,root_path,owner,group,after_id)) {
        ferr="plan_failed"; goto fail;
    }
    (void)oc_close(awfd); awfd=-1;
    oc_rm_subdir(data_fd,aw_leaf); aw_leaf[0]=0;
    if ((oc_equal(new_prefs.base,"1") || oc_equal(new_prefs.touch,"2")) &&
        !oc_check_active_pins(root,data_fd,pkg_id,after_id,new_prefs.base,new_prefs.touch,&ferr)) goto fail;

    /* 9. Transactional prepare + reconcile (caller api runs GC under lock_fd). */
    char prep_nonce[33];
    if (!oc_transaction_prepare(root,data_fd,work_rec,"install",before_id,after_id,base_id,
                                0,owner,group,prep_nonce)) {
        ferr="record_rename_failed"; goto fail;
    }
    work_rec[2]=prep_nonce;
    if (!oc_transaction_reconcile(root,root_path,data_fd,work_rec,session_dir,prep_nonce,
                                  owner,group,&ferr)) goto fail;

fail:
    if (awfd>=0) (void)oc_close(awfd);
    if (aw_leaf[0] && data_fd>=0 && !init_leaf[0]) oc_rm_subdir(data_fd,aw_leaf);
    if (data_fd>=0) (void)oc_close(data_fd);
    if (init_leaf[0] && parent_fd>=0) oc_rm_subdir(parent_fd,init_leaf);
    if (parent_fd>=0) (void)oc_close(parent_fd);
    return ferr ? cerr(err_out,ferr) : 1;
}
