/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Native settled-boot selector: policy load, feature staging, durable debit,
 * RAM publication, and base read-ahead tuning.
 */
#include "oc-core.h"

OcBoot oc_boot;

static const char *const oc_ui_alias_names[3]={"v.xml","vui-hold.so","vui-plugins"};

void oc_stamp(OcBoot *b, const char *phase) {
    char tick[96], line[160];
    if (b->time_count>=12 || oc_text(b->root,"proc/uptime",tick,sizeof tick,1)<0) return;
    unsigned n=0;
    while (tick[n] && tick[n]!=' ') {
        if (!((tick[n]>='0'&&tick[n]<='9')||tick[n]=='.')) return;
        ++n;
    }
    if (!n||tick[n]!=' ') return;
    tick[n]=0;
    if (!oc_join(line,sizeof line,phase,"|")||!oc_join(line,sizeof line,line,tick)||
        !oc_join(line,sizeof line,line,"\n")||!oc_join(b->times,sizeof b->times,b->times,line)) return;
    ++b->time_count;
}

static int oc_gate(OcBoot *b, int release) {
    if (!b->gated||b->gate_sent) return 1;
    b->gate_sent=1;
    if (b->parent<=1||oc_parent()!=b->parent) return 0;
    char frame=release?'G':'J';
    int ok=oc_write_all(1,&frame,1);
    if (oc_close(1)<0) ok=0;
    if (ok&&release) { b->released=1; oc_stamp(b,"gate_released"); oc_cut("gate_released"); }
    return ok;
}

static int oc_boot_identity(OcBoot *b) {
    if (oc_absent_at(b->ram,"boot-id")) {
        char digest[65];
        if (oc_text(b->root,"proc/sys/kernel/random/boot_id",b->boot,sizeof b->boot,1)<0||
            !oc_one_line(b->boot)||!oc_uuid(b->boot)) return 0;
        OcHash hash;
        oc_hash_init(&hash);
        const char *parts[]={"OCBOOT1",b->boot,b->record_fields[2],b->record_fields[11],b->record_fields[10]};
        for (unsigned i=0; i<5; ++i) {
            oc_hash_add(&hash,parts[i],oc_length(parts[i]));
            oc_hash_add(&hash,i==4?"\n":"|",1);
        }
        oc_hash_finish(&hash,digest);
        unsigned at=0;
        for (unsigned i=0; i<36; ++i) b->boot[i]=(i==8||i==13||i==18||i==23)?'-':digest[at++];
        for (unsigned i=0; i<16; ++i) {
            if (!oc_equal(b->boot,b->record_fields[11])&&!oc_equal(b->boot,b->record_fields[10])) break;
            b->boot[0]="0123456789abcdef"[i];
        }
        if (oc_symlink(b->boot,b->ram,"boot-id")<0) return 0;
    }
    OcMeta meta;
    if (oc_metadata(b->ram,"boot-id",&meta)<0||(meta.mode&OC_TYPE)!=0120000||
        meta.uid!=(unsigned)b->owner||meta.gid!=(unsigned)b->group||
        oc_readlink(b->ram,"boot-id",b->boot,sizeof b->boot)!=36) return 0;
    b->boot[36]=0;
    return oc_uuid(b->boot);
}

static int oc_copy_input(OcBoot *b, const char *key, int output, const char *name, unsigned mode) {
    OcInput *row=oc_find(b,key);
    if (!row||row->absent) { b->input_failure=1; return 0; }
    int parent=b->root;
    const char *path=row->path;
    if (oc_prefix(path,"@/")) { parent=b->snapshot; path+=2; }
    else ++path;
    long input=oc_beneath(parent,path,OC_READ,0);
    if (input<0) { b->input_failure=1; return 0; }
    long target=-1;
    if (output>=0) {
        target=oc_openat(output,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,mode);
        if (target<0) { (void)oc_close((int)input); return 0; }
    }
    char digest[65]; OcMeta actual;
    int copied=oc_hash_copy((int)input,(int)target,33554432,digest,&actual);
    int ok=copied==OC_COPY_OK;
    if (copied==OC_COPY_SOURCE) b->input_failure=1;
    if (ok && (!oc_equal(digest,row->digest)||!oc_meta_row_equal(row->key,&row->meta,&actual))) {
        b->input_failure=1; ok=0;
    }
    if (ok && target>=0) ok=oc_mode((int)target,mode)>=0;
    if (oc_close((int)input)<0) { b->input_failure=1; ok=0; }
    if (target>=0 && oc_close((int)target)<0) ok=0;
    return ok;
}

static int oc_reseal_hint(OcBoot *b) {
    long fd=oc_openat(b->data,"reseal",OC_READ,0);
    if (fd==-2) return 0;
    if (fd<0) return -1;
    OcMeta before, after; char text[66];
    int ok=oc_stat((int)fd,&before)>=0 && before.mode==(OC_REGULAR|0600) && before.size==65 &&
        before.uid==(unsigned)b->owner && before.gid==(unsigned)b->group;
    if (ok) ok=oc_text_fd((int)fd,text,sizeof text)==65 && oc_one_line(text) && oc_hex(text,64) &&
        oc_stat((int)fd,&after)>=0 && oc_meta_equal(&before,&after);
    if (oc_close((int)fd)<0) ok=0;
    return ok?oc_equal(text,b->record_fields[5]):-1;
}

static int oc_request_reseal(OcBoot *b) {
    for (unsigned i=0; i<b->input_count; ++i) {
        OcInput *row=&b->inputs[i];
        if (!row->absent && !oc_copy_input(b,row->key,-1,0,0)) return 0;
    }
    if (oc_reseal_hint(b)<0||!oc_random(b->root,b->nonce)) return 0;
    char name[64], text[66];
    if (!oc_join(name,sizeof name,".reseal-",b->nonce)||!oc_join(text,sizeof text,b->record_fields[5],"\n")) return 0;
    long fd=oc_openat(b->data,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,text,65)&&oc_mode((int)fd,0600)>=0&&oc_sync((int)fd)>=0;
    oc_cut("reseal_synced");
    if (oc_close((int)fd)<0) ok=0;
    if (ok) ok=oc_rename(b->data,name,"reseal")>=0&&oc_sync(b->data)>=0;
    if (!ok) (void)oc_unlink(b->data,name);
    oc_cut("reseal_published");
    return ok;
}

static int oc_package_copy(OcBoot *b, const char *name, int output, const char *destination, unsigned mode) {
    char key[192];
    return oc_join(key,sizeof key,"package-",b->record_fields[3]) && oc_join(key,sizeof key,key,"/") &&
        oc_join(key,sizeof key,key,name) && oc_copy_input(b,key,output,destination,mode);
}

static int oc_composed_copy(OcBoot *b, const char *name, int output, unsigned mode) {
    char key[192];
    return oc_join(key,sizeof key,"composed-",b->record_fields[3]) && oc_join(key,sizeof key,key,"/") &&
        oc_join(key,sizeof key,key,name) && oc_copy_input(b,key,output,name,mode);
}

static int oc_composed_link(OcBoot *b, const char *name) {
    char key[192], target[192];
    return oc_join(key,sizeof key,"composed-",b->record_fields[3]) &&
        oc_join(key,sizeof key,key,"/") && oc_join(key,sizeof key,key,name) &&
        oc_copy_input(b,key,-1,0,0) &&
        oc_join(target,sizeof target,"../../mnt/data_persist/open-connect/composed/",b->record_fields[3]) &&
        oc_join(target,sizeof target,target,"/") && oc_join(target,sizeof target,target,name) &&
        oc_symlink(target,b->stage,name)>=0;
}

int oc_ui_stage(OcBoot *b) {
    int base=oc_equal(b->flags[6],"1"), warning=oc_equal(b->flags[2],"1");
    if (warning&&!oc_composed_link(b,"uia.so")) return 0;
    if ((base||warning)&&(!oc_composed_copy(b,"mmui.so",b->stage,0600)||
        !oc_copy_input(b,"current/mmui.xml",b->stage,"mmui.xml",0600))) return 0;
    if (!base) return 1;
    if (!oc_composed_copy(b,"vui.so",b->stage,0600)||!oc_composed_copy(b,"vui.xml",b->stage,0600)||
        oc_mkdir(b->stage,"vui-plugins",0700)<0) return 0;
    long folder=oc_open_private(b->stage,"vui-plugins");
    if (folder<0) return 0;
    int ok=1;
    for (char *name=b->plugins; *name; name+=oc_length(name)+1) {
        char path[192];
        if (!oc_join(path,sizeof path,"/jci/vui/plugins/",name)||oc_symlink(path,(int)folder,name)<0) { ok=0; break; }
    }
    if (oc_close((int)folder)<0) ok=0;
    return ok && oc_symlink("feature/vui-plugins",b->stage,".vui-link")>=0;
}

static void oc_ui_unwind(OcBoot *b) {
    for (unsigned i=0; i<3; ++i) if (b->ui_aliases&(1u<<i)) {
        OcMeta now;
        if ((b->ui_aliases&(8u<<i)) ||
            (oc_metadata(b->ram,oc_ui_alias_names[i],&now)>=0 &&
             now.device==b->ui_identity[i].device && now.inode==b->ui_identity[i].inode))
            (void)oc_unlink(b->ram,oc_ui_alias_names[i]);
    }
}

static int oc_ui_alias(OcBoot *b) {
    if (!b->selected||!oc_equal(b->flags[6],"1")) return 1;
    const char *sources[]={"vui.xml","vui.so",".vui-link"};
    for (unsigned i=0; i<3; ++i) {
        if (oc_metadata(b->stage,sources[i],&b->ui_identity[i])<0) return 0;
        b->ui_aliases|=1u<<i;
        if (oc_link(b->stage,sources[i],b->ram,oc_ui_alias_names[i])<0) return 0;
        b->ui_aliases|=8u<<i;
    }
    return oc_unlink(b->stage,".vui-link")>=0;
}

static int oc_budget_policy(OcBoot *b) {
    char acc[8], nvram[16];
    if (oc_text(b->root,"sys/class/gpio/ACC_Sense/value",acc,sizeof acc,1)<0||
        !oc_one_line(acc)||!oc_bit(acc)||!oc_nvram(b,nvram)||!oc_equal(nvram,b->flags[3])) return 0;
    unsigned budget=(unsigned)(b->record_fields[9][0]-'0');
    if (!oc_equal(b->record_fields[10],"-") && !oc_equal(b->record_fields[10],b->boot) && oc_equal(acc,"1")) budget=3;
    b->selected=budget>0;
    const char *wanted=b->base_flags[3];
    if (b->selected && oc_equal(b->flags[1],"1")) wanted="disable";
    if (!oc_equal(wanted,nvram)) return 0;
    b->record_fields[9]=budget?(budget==3?"2":budget==2?"1":"0"):"0";
    b->record_fields[10]="-";
    b->record_fields[11]=b->boot;
    return 1;
}

static int oc_token(OcBoot *b) {
    if (oc_absent_at(b->ram,"token")) {
        if (!oc_random(b->root,b->token)) return 0;
        b->token[32]='\n'; b->token[33]=0;
        if (!oc_new_text(b->ram,"token",b->token,0600)) return 0;
    } else if (oc_text(b->ram,"token",b->token,sizeof b->token,0)!=33) return 0;
    if (b->token[32]!='\n') return 0;
    b->token[32]=0;
    return oc_hex(b->token,32);
}

static int oc_stage(OcBoot *b) {
    if (!oc_random(b->root,b->nonce)||!oc_join(b->observer_name,sizeof b->observer_name,".ignition-",b->nonce)||
        oc_mkdir(b->ram,b->observer_name,0700)<0) return 0;
    b->observer=oc_open_private(b->ram,b->observer_name);
    if (b->observer<0 || !oc_package_copy(b,"ignition",b->observer,"ignition",0700)||
        !oc_package_copy(b,"flush",b->observer,"flush",0700)) return 0;
    if (!b->selected) return 1;
    if (!oc_token(b)||!oc_join(b->stage_name,sizeof b->stage_name,".feature-",b->nonce)||oc_mkdir(b->ram,b->stage_name,0700)<0) return 0;
    b->stage=oc_open_private(b->ram,b->stage_name);
    if (b->stage<0||!oc_copy_input(b,"current/sm-normal.conf",b->stage,"sm.conf",0600)||
        !oc_copy_input(b,"current/sm-wcp.conf",b->stage,"sm_WCP.conf",0600)) return 0;
    if (oc_equal(b->flags[1],"2") && !oc_package_copy(b,"touch-disable.so",b->stage,"touch-disable.so",0755)) return 0;
    if (!oc_ui_stage(b)) return 0;
    if (oc_equal(b->flags[6],"1") && oc_equal(b->flags[7],"1") &&
        (!oc_package_copy(b,"defer-gap2.sh",b->stage,"defer-gap2.sh",0600)||
         !oc_package_copy(b,"defer-nav.sh",b->stage,"defer-nav.sh",0600))) return 0;
    const char *ui[]={"runtime.js","dialog.js","settings.js"};
    for (unsigned i=0; i<3; ++i) if (!oc_package_copy(b,ui[i],b->stage,ui[i],0600)) return 0;
    if (oc_equal(b->record_fields[12],"installed")) {
        char target[192];
        if (!oc_package_copy(b,"maintenance.js",-1,0,0)||
            !oc_join(target,sizeof target,"../../mnt/data_persist/open-connect/packages/",b->record_fields[3])||
            !oc_join(target,sizeof target,target,"/maintenance.js")||
            oc_symlink(target,b->stage,"maintenance.js")<0) return 0;
    }
    if (oc_equal(b->flags[8],"1") && !oc_package_copy(b,"carplay.js",b->stage,"carplay.js",0600)) return 0;
    if (!oc_package_copy(b,"service.sh",b->stage,"service.sh",0600)) return 0;
    if (oc_equal(b->flags[7],"1")) {
        if (!oc_package_copy(b,"wireless.sh",b->stage,"wireless.sh",0600)||
            !oc_package_copy(b,"wireless-device.awk",b->stage,"wireless-device.awk",0600)||
            !oc_join(b->scratch,sizeof b->scratch,b->boot,"\n")||
            !oc_new_text(b->stage,"boot-id",b->scratch,0600)||!oc_new_text(b->stage,"wireless-applied","0\n",0600)) return 0;
    }
    char version[64];
    if (!oc_saved_text(b->package,&b->pkg,"VERSION",version,sizeof version)||!oc_one_line(version)) { b->input_failure=1; return 0; }
    for (const char *p=version; *p; ++p) if (!((*p>='0'&&*p<='9')||(*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||*p=='.'||*p=='-')) return 0;
    if (!oc_saved_text(b->snapshot,&b->current,"index.html",b->scratch,sizeof b->scratch)) { b->input_failure=1; return 0; }
    char output[32768]; unsigned used=0, slots[4]={0,0,0,0};
    const char *needles[]={"@TOKEN@","@VERSION@","@NOTICE@","@BOOT@"};
    const char *values[]={b->token,version,b->record_fields[12],b->boot};
    for (const char *p=b->scratch; *p;) {
        unsigned i=0;
        while (i<4 && !oc_prefix(p,needles[i])) ++i;
        if (i<4) {
            unsigned n=oc_length(values[i]);
            if (used+n>=sizeof output) return 0;
            for (unsigned j=0; j<n; ++j) output[used++]=values[i][j];
            ++slots[i]; p+=oc_length(needles[i]);
        } else { if (used+1>=sizeof output) return 0; output[used++]=*p++; }
    }
    output[used]=0;
    if (slots[0]!=1||slots[1]!=1||slots[2]!=1||slots[3]>1||
        (oc_equal(b->flags[8],"1")&&slots[3]!=1)) { b->input_failure=1; return 0; }
    if (!oc_new_text(b->stage,"index.html",output,0600)) return 0;
    return 1;
}

static int oc_log_stage(OcBoot *b) {
    if (!b->selected||!oc_equal(b->flags[6],"1")) return 1;
    const char *paths[]={"tmp/common","tmp/common/log"};
    for (unsigned i=0; i<2; ++i) {
        long fd=oc_beneath(b->root,paths[i],OC_DIRECTORY,0);
        if (fd==-2) {
            if (oc_mkdir(b->root,paths[i],0755)<0) return 0;
            fd=oc_beneath(b->root,paths[i],OC_DIRECTORY,0);
        }
        if (fd<0) return 0;
        OcMeta meta;
        int ok=oc_stat((int)fd,&meta)>=0 && meta.uid==(unsigned)b->owner && !(meta.mode&0022);
        if (i==1) b->log=(int)fd;
        else if (oc_close((int)fd)<0) ok=0;
        if (!ok) return 0;
    }
    return oc_absent_at(b->log,"settings.txt") && oc_join(b->log_name,sizeof b->log_name,".open-connect-log-",b->nonce) &&
        oc_new_text(b->log,b->log_name,"COMMON_LOG_LEVEL=Warn\n",0644);
}

static int oc_publish(OcBoot *b) {
    if (b->gated&&oc_parent()!=b->parent) return 0;
    if (!oc_absent_at(b->ram,"selected")||!oc_absent_at(b->ram,"feature")||!oc_absent_at(b->ram,"ignition")) return 0;
    char selected[66];
    if (!oc_join(selected,sizeof selected,b->record_fields[5],"\n")||
        !oc_new_text(b->ram,".native-selected",selected,0600)) return 0;
    if (b->access_present && !oc_new_text(b->ram,"access-selected",selected,0600)) return 0;
    oc_cut("before_publication");
    if (oc_block()<0) return 0;
    oc_cut("publication");
    if (!oc_ui_alias(b)) return 0;
    if (oc_rename(b->ram,b->observer_name,"ignition")<0) return 0;
    if (!b->selected) return 1;
    if (oc_rename(b->ram,b->stage_name,"feature")<0) return 0;
    if (b->log>=0 && oc_link(b->log,b->log_name,b->log,"settings.txt")<0) return 0;
    if (oc_link(b->ram,".native-selected",b->ram,"selected")<0) {
        if (b->log>=0) {
            long fd=oc_openat(b->log,"settings.txt",OC_READ,0), held=oc_openat(b->log,b->log_name,OC_READ,0);
            OcMeta a, c;
            if (fd>=0&&held>=0&&oc_stat((int)fd,&a)>=0&&oc_stat((int)held,&c)>=0&&a.device==c.device&&a.inode==c.inode)
                (void)oc_unlink(b->log,"settings.txt");
            if (fd>=0) (void)oc_close((int)fd);
            if (held>=0) (void)oc_close((int)held);
        }
        return 0;
    }
    (void)oc_unlink(b->ram,".native-selected");
    if (b->log>=0) (void)oc_unlink(b->log,b->log_name);
    return 1;
}

static int oc_base_read_ahead(OcBoot *b) {
    if (!b->selected||!oc_equal(b->flags[6],"1")) return 1;
    char value[16];
    if (oc_text(b->root,"sys/devices/virtual/block/ffx01/dev",value,sizeof value,0)<0||
        !oc_equal(value,"253:16\n")) return 0;
    long queue=oc_beneath(b->root,"sys/devices/virtual/block/ffx01/queue",OC_DIRECTORY,0);
    if (queue<0) return 0;
    int ok=oc_text((int)queue,"read_ahead_kb",value,sizeof value,0)>=0;
    if (ok && oc_equal(value,"128\n")) {
        long fd=oc_openat((int)queue,"read_ahead_kb",OC_WRITE,0);
        OcMeta meta;
        ok=fd>=0 && oc_stat((int)fd,&meta)>=0 && meta.mode==(OC_REGULAR|0644) &&
            meta.uid==(unsigned)b->owner && meta.gid==(unsigned)b->group && oc_write_all((int)fd,"4\n",2);
        if (fd>=0 && oc_close((int)fd)<0) ok=0;
        if (ok) ok=oc_text((int)queue,"read_ahead_kb",value,sizeof value,0)>=0;
    }
    ok=ok && oc_equal(value,"4\n");
    if (oc_close((int)queue)<0) ok=0;
    return ok;
}

int oc_policy_load(OcBoot *b) {
    char path[192];
    if (!oc_join(path,sizeof path,"snapshots/",b->record_fields[5])) return 0;
    b->snapshot=oc_open_private(b->data,path);
    if (!oc_join(path,sizeof path,"snapshots/",b->record_fields[4])) return 0;
    b->baseline=oc_open_private(b->data,path);
    if (b->snapshot<0||b->baseline<0||
        !oc_load_manifest(b->snapshot,b->record_fields[5],b->current_manifest,sizeof b->current_manifest,&b->current)||
        !oc_load_manifest(b->baseline,b->record_fields[4],b->base_manifest,sizeof b->base_manifest,&b->base)||
        !oc_saved_text(b->snapshot,&b->current,"config",b->config,sizeof b->config)||
        !oc_config(b,b->config,b->flags,1,b->svc_digest)||!oc_equal(b->flags[0],b->record_fields[3])||
        !oc_saved_text(b->baseline,&b->base,"config",b->base_config,sizeof b->base_config)||
        !oc_config(b,b->base_config,b->base_flags,0,0)) return 0;
    return 1;
}

int oc_load(OcBoot *b) {
    char path[192];
    if (!oc_join(path,sizeof path,"packages/",b->record_fields[3])) return 0;
    b->package=oc_open_private(b->data,path);
    if (!oc_join(path,sizeof path,"composed/",b->record_fields[3])) return 0;
    b->composed=oc_open_private(b->data,path);
    if (b->package<0||b->composed<0||
        !oc_load_manifest(b->package,b->record_fields[3],b->package_manifest,sizeof b->package_manifest,&b->pkg)||b->pkg.count>64) return 0;
    const char *mandatory[]={"boot-select","service.sh",
        "ignition","flush","api","install","runtime.js","dialog.js","settings.js","VERSION","INSTANCE",
        "preferences.awk","services.tsv","sm-profile.awk"};
    for (unsigned i=0; i<sizeof mandatory/sizeof *mandatory; ++i) if (!oc_digest(&b->pkg,mandatory[i])) return 0;
    b->access_present=oc_digest(&b->current,"access")!=0;
    b->base_access_present=oc_digest(&b->base,"access")!=0;
    if (b->access_present && (!oc_saved_text(b->snapshot,&b->current,"access",b->access,sizeof b->access)||!oc_access(b->access,b->access_fields))) return 0;
    if (b->base_access_present && (!oc_saved_text(b->baseline,&b->base,"access",b->base_access,sizeof b->base_access)||!oc_access(b->base_access,b->base_access_fields))) return 0;
    if (!oc_plan(b)||!oc_join(path,sizeof path,"composed-",b->record_fields[3])||!oc_join(path,sizeof path,path,"/files.sha256")) return 0;
    OcInput *composition=oc_find(b,path);
    if (!composition||!oc_hex(composition->digest,64)||!oc_join(b->composed_digest,sizeof b->composed_digest,"",composition->digest)||
        !oc_load_manifest(b->composed,b->composed_digest,b->composed_manifest,sizeof b->composed_manifest,&b->composition)||
        b->composition.count!=sizeof oc_composed_names/sizeof *oc_composed_names) return 0;
    for (unsigned i=0; i<sizeof oc_composed_names/sizeof *oc_composed_names; ++i) if (!oc_digest(&b->composition,oc_composed_names[i])) return 0;
    return oc_dependency_coverage(b)&&oc_snapshot_coverage(b)&&oc_access_coverage(b)&&oc_identity_coverage(b);
}

static int oc_select(OcBoot *b, int root) {
    b->root=root; b->data=b->ram=b->lock=b->snapshot=b->baseline=b->package=b->composed=b->stage=b->observer=b->log=-1;
    b->owner=oc_owner(); b->group=oc_group();
    b->parent=oc_parent();
    if (b->gated&&(b->parent<=1||oc_watch_parent()<0||oc_parent()!=b->parent)) return OC_REFUSE;
#ifndef OC_HOST
    if (b->owner!=0||b->group!=0) return OC_REFUSE;
#endif
    if (b->gated&&oc_worker_cpu1()<0) return OC_SLOW;
    b->data=oc_open_private(root,OC_DATA);
    if (b->data<0) return OC_SLOW;
    long ram=oc_beneath(root,OC_RAM,OC_DIRECTORY,0);
    if (ram==-2) {
        if (oc_mkdir(root,OC_RAM,0700)<0) return OC_REFUSE;
        ram=oc_beneath(root,OC_RAM,OC_DIRECTORY,0);
    }
    b->ram=(int)ram;
    if (b->ram<0||!oc_private(b->ram)) return OC_REFUSE;
    oc_stamp(b,"hook_entry");
    if (b->gated) oc_stamp(b,"worker_cpu1");
    b->lock=(int)oc_openat(b->ram,"lock",OC_RW|OC_CREATE,0600);
    OcMeta lock_meta;
    if (b->lock<0||oc_stat(b->lock,&lock_meta)<0||lock_meta.mode!=(OC_REGULAR|0600)||
        lock_meta.uid!=(unsigned)b->owner||lock_meta.gid!=(unsigned)b->group||oc_lock(b->lock)<0) return OC_REFUSE;
    if (!oc_record_file(b,0,0)) return OC_SLOW;
    if (!oc_boot_identity(b)) return OC_REFUSE;
    if (oc_equal(b->record_fields[11],b->boot)||!oc_absent_at(b->ram,"selected")||
        !oc_absent_at(b->ram,"feature")||!oc_absent_at(b->ram,"ignition")||!oc_absent_at(b->ram,"access-selected")||
        !oc_absent_at(b->ram,".native-selected")) return OC_REFUSE;
    if (!oc_mounts(b)||!oc_policy_load(b)) return OC_SLOW;
    if (oc_equal(b->flags[6],"1")) for (unsigned i=0; i<3; ++i)
        if (!oc_absent_at(b->ram,oc_ui_alias_names[i])) return OC_REFUSE;
    if (b->gated) {
        int hint=oc_reseal_hint(b);
        if (hint<0) return OC_REFUSE;
        if (hint) return OC_SLOW;
    }
    if (!oc_budget_policy(b)) return OC_SLOW;
    if (b->gated) {
        oc_stamp(b,"policy_checked");
        if (!oc_gate(b,1)) return OC_REFUSE;
    }
    if (!oc_load(b)) return OC_SLOW;
    if (b->metadata_drift) {
        (void)oc_request_reseal(b);
        return OC_SLOW;
    }
    oc_stamp(b,"inputs_checked");
    if (!oc_stage(b)) return b->input_failure?OC_SLOW:OC_REFUSE;
    if (!oc_log_stage(b)) return OC_REFUSE;
    oc_stamp(b,"feature_copied");
    if (b->gated&&oc_parent()!=b->parent) return OC_REFUSE;
    if (!oc_record_commit(b)) return OC_REFUSE;
    if (!oc_publish(b)) return OC_REFUSE;
    if (!oc_base_read_ahead(b)) oc_stamp(b,"base_read_ahead_unavailable");
    oc_stamp(b,"selector_exit");
    (void)oc_new_text(b->ram,"startup-times",b->times,0600);
    return b->selected?0:OC_STOCK;
}

int oc_record_commit(OcBoot *b) {
    if (!oc_random(b->root,b->nonce)) return 0;
    b->record_fields[2]=b->nonce; b->record_fields[8]="-";
    b->next[0]=0;
    for (unsigned i=0; i<13; ++i)
        if (!oc_join(b->next,sizeof b->next,b->next,b->record_fields[i]) ||
            !oc_join(b->next,sizeof b->next,b->next,i==12?"\n":"|")) return 0;
    char name[64];
    if (!oc_join(name,sizeof name,"record.",b->nonce)) return 0;
    long fd=oc_openat(b->data,name,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
    if (fd<0) return 0;
    int ok=oc_write_all((int)fd,b->next,oc_length(b->next)) && oc_mode((int)fd,0600)>=0;
    oc_stamp(b,"record_written"); oc_cut("record_written");
    if (ok) ok=oc_sync((int)fd)>=0;
    oc_stamp(b,"record_synced"); oc_cut("record_synced");
    if (oc_close((int)fd)<0) ok=0;
    if (!ok) return 0;
    if (oc_rename(b->data,name,"record")<0) return 0;
    b->debited=1;
    oc_stamp(b,"record_renamed"); oc_cut("record_renamed");
    if (oc_sync(b->data)<0) return 0;
    oc_stamp(b,"directory_synced"); oc_cut("directory_synced");
    if (oc_text(b->data,"record",b->scratch,sizeof b->scratch,0)<0 || !oc_equal(b->scratch,b->next)) return 0;
    return 1;
}

void oc_close_boot(OcBoot *b) {
    int handles[]={b->log,b->observer,b->stage,b->composed,b->package,
        b->baseline,b->snapshot,b->lock,b->ram,b->data};
    for (unsigned i=0; i<sizeof handles/sizeof *handles; ++i) if (handles[i]>=0) (void)oc_close(handles[i]);
}

int oc_selection(int root, int gated) {
    oc_boot.gated=gated;
    int result=oc_select(&oc_boot,root);
    if (gated&&!oc_boot.gate_sent&&!oc_gate(&oc_boot,0)) result=OC_REFUSE;
    if (oc_boot.released&&result==OC_SLOW) {
        (void)oc_write_all(2,"late_verification_refused\n",26);
        result=OC_REFUSE;
    }
    if (result!=0) oc_ui_unwind(&oc_boot);
    oc_close_boot(&oc_boot);
    return result;
}
