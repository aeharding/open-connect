/* SPDX-License-Identifier: AGPL-3.0-or-later
 * One bounded POST request on stdin/stdout, launched by BusyBox tcpsvd.
 * Interactive Settings/USB requests run natively via core/oc-api.c; cold
 * maintenance transactions exec the verified shell backend.
 */
#include "core/oc-core.h"

static long token_read(const char *p, char *b, unsigned n) {
    long f=oc_openat(OC_CWD,p,OC_READ|OC_BLOCKING,0);
    if (f<0) return -1;
    long r=oc_read((int)f,b,n);
    (void)oc_close((int)f);
    return r;
}
static int lower(int c) { return c>='A'&&c<='Z'?c+32:c; }
static int header(const char *a,const char *b) {
    while(*b&&lower(*a)==*b){a++;b++;} return !*b;
}
static int session_closed(const char *token_path) {
    char path[512]; unsigned parent=oc_length(token_path);
    while(parent&&token_path[parent-1]!='/')parent--;
    if(!parent||parent+7>sizeof path)return 1;
    for(unsigned i=0;i<parent;i++)path[i]=token_path[i];
    if(!oc_join(path+parent,sizeof path-parent,"","closed"))return 1;
    OcMeta m;
    return oc_metadata(OC_CWD,path,&m)>=0;
}
static int send_text(const char *s) { return oc_write_all(1,s,oc_length(s)); }
static unsigned parent_len(const char *p,unsigned n) {
    while(n&&p[n-1]!='/')n--;
    return n?n-1:0;
}
static int path_join(char *out,unsigned cap,const char *p,unsigned n,const char *tail) {
    if(n>=cap)return 0;
    for(unsigned i=0;i<n;i++)out[i]=p[i];
    return oc_join(out+n,cap-n,"",tail);
}
static int linked(const char *p,char *value,unsigned cap) {
    long n=oc_readlink(OC_CWD,p,value,cap-1);
    if(n<=0||(unsigned)n>=cap-1)return 0;
    value[n]=0;return 1;
}
/* Discovery only: the runner offers one immutable pair after its final entry
 * checks. The installed listener never executes shell or takes the writer lock.
 * Capture one canonical session, then fence the pointer before returning it. */
static void media_offer(const char *token_path) {
    char path[512],usb[512],check[512],offer[49],token[34];
    unsigned home=parent_len(token_path,oc_length(token_path));
    unsigned root=parent_len(token_path,parent_len(token_path,home));
    if(!root||!path_join(path,sizeof path,token_path,root,"/runtime")||
       !linked(path,check,sizeof check)||oc_length(check)!=home||!oc_prefix(token_path,check))goto miss;
    if(!path_join(path,sizeof path,token_path,root,"/usb-runtime")||
       !linked(path,usb,sizeof usb)||oc_length(usb)!=root+24||
       !path_join(path,sizeof path,token_path,root,"/sessions/session-")||
       !oc_prefix(usb,path))goto miss;
    for(unsigned i=root+18;i<root+24;i++)
        if(!((usb[i]>='a'&&usb[i]<='z')||(usb[i]>='A'&&usb[i]<='Z')||
             (usb[i]>='0'&&usb[i]<='9')))goto miss;
    unsigned n=oc_length(usb);
    if(!path_join(path,sizeof path,usb,n,"/offer")||token_read(path,offer,sizeof offer)!=48||
       offer[14]!='|'||offer[47]!='\n')goto miss;
    offer[14]=0;offer[47]=0;
    if(!oc_equal(offer,usb+root+10)||!oc_hex(offer+15,32)||
       !path_join(path,sizeof path,usb,n,"/token")||token_read(path,token,sizeof token)!=33||
       token[32]!='\n'||session_closed(path))goto miss;
    token[32]=0;
    if(!oc_equal(token,offer+15)||!path_join(path,sizeof path,token_path,root,"/usb-runtime")||
       !linked(path,check,sizeof check)||!oc_equal(check,usb))goto miss;
    send_text("{\"ok\":true,\"media\":{\"session\":\"");send_text(offer);
    send_text("\",\"token\":\"");send_text(token);send_text("\"}}\n");return;
miss:
    send_text("{\"ok\":true,\"media\":null}\n");
}
static int response(int code,const char *error) {
    if(!send_text(code==200?"HTTP/1.0 200 OK\r\n":
                  code==403?"HTTP/1.0 403 Forbidden\r\n":"HTTP/1.0 400 Bad Request\r\n"))return 0;
    if(!send_text("Content-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n"
                  "Cache-Control: no-store\r\nConnection: close\r\n\r\n"))return 0;
    if(error){send_text("{\"ok\":false,\"error\":\"");send_text(error);send_text("\"}\n");}
    return 1;
}
static int run(int argc,char **argv) {
    if(argc>=2&&argv[1][0]=='-'&&argv[1][1]=='-')return oc_api_cli(argc,argv);
    if(argc!=3||argv[1][0]!='/'||argv[2][0]!='/')return 64;
    char bytes[4097], token[34]; unsigned used=0, boundary=0, size=0;
    while(!boundary){
        if(used==4096){response(400,"headers_too_large");return 1;}
        long n=oc_read(0,bytes+used,4096-used);
        if(n==-4)continue;
        if(n<=0)return 1;
        used+=(unsigned)n;
        for(unsigned i=3;i<used;i++)
            if(bytes[i-3]=='\r'&&bytes[i-2]=='\n'&&bytes[i-1]=='\r'&&bytes[i]=='\n'){boundary=i+1;break;}
    }
    bytes[used]=0;
    char *line=bytes; unsigned lengths=0, types=0;
    for(unsigned i=0;i<boundary-2;i++) {
        if(bytes[i]=='\r'&&bytes[i+1]=='\n'){
            bytes[i]=0;
            if(line==bytes){
                if(!oc_equal(line,"POST /control HTTP/1.1")&&!oc_equal(line,"POST /control HTTP/1.0"))goto bad;
            }else if(header(line,"content-length:")){
                if(++lengths!=1)goto bad;
                char *p=line+15; while(*p==' '||*p=='\t')p++;
                if(*p<'0'||*p>'9')goto bad;
                for(;*p>='0'&&*p<='9';p++){size=size*10+(unsigned)(*p-'0');if(size>256)goto bad;}
                while(*p==' '||*p=='\t')p++;
                if(*p)goto bad;
            }else if(header(line,"content-type:")){
                if(++types!=1)goto bad;
                char *p=line+13; while(*p==' '||*p=='\t')p++;
                if(!oc_equal(p,"text/plain")&&!oc_equal(p,"text/plain;charset=UTF-8")&&
                   !oc_equal(p,"text/plain; charset=UTF-8"))goto bad;
            }else if(header(line,"transfer-encoding:")||header(line,"expect:"))goto bad;
            line=bytes+i+2; i++;
        }else if(!bytes[i]||((unsigned char)bytes[i]<32&&bytes[i]!='\t'))goto bad;
    }
    if(lengths!=1||types!=1||size<43||boundary+size>4096||used>boundary+size)goto bad;
    while(used<boundary+size){
        long n=oc_read(0,bytes+used,boundary+size-used);
        if(n==-4)continue;
        if(n<=0)return 1;
        used+=(unsigned)n;
    }
    bytes[used]=0;
    char *fields[6]; fields[0]=bytes+boundary; unsigned count=1;
    for(unsigned i=boundary;i<used;i++){
        if(bytes[i]=='|'){
            if(count==6||i==boundary||bytes[i-1]==0)goto bad;
            bytes[i]=0;fields[count++]=bytes+i+1;
        }else if(!((bytes[i]>='a'&&bytes[i]<='z')||(bytes[i]>='0'&&bytes[i]<='9')||bytes[i]=='-'))goto bad;
    }
    if(count!=6||!fields[5][0]||!oc_hex(fields[0],32)||
       (!oc_equal(fields[1],"-")&&!oc_hex(fields[1],32)&&!oc_hex(fields[1],64)))goto bad;
    if(token_read(argv[1],token,sizeof token)!=33||token[32]!='\n')return response(403,"unauthorized"),1;
    token[32]=0;
    if(!oc_equal(token,fields[0]))return response(403,"unauthorized"),1;
    const char *op=fields[2];
    if(oc_equal(op,"set")){
        unsigned n=0;
        for(const char *p=fields[3];*p;++p) {
            if(++n>32||((*p<'a'||*p>'z')&&!(n>1&&((*p>='0'&&*p<='9')||*p=='-'))))goto bad;
        }
        int touch=oc_equal(fields[3],"touch");
        if(!n||(!oc_equal(fields[4],"0")&&!oc_equal(fields[4],"1")&&!(touch&&oc_equal(fields[4],"2")))||
           (!oc_equal(fields[5],"0")&&!oc_equal(fields[5],"1")&&!(touch&&oc_equal(fields[5],"2"))))goto bad;
    }else{
        if(!oc_equal(op,"status")&&!oc_equal(op,"install")&&!oc_equal(op,"uninstall")&&
           !oc_equal(op,"restart")&&!oc_equal(op,"dismiss")&&!oc_equal(op,"recover")&&!oc_equal(op,"import"))goto bad;
        if((!oc_equal(fields[3],"-")&&
            !(oc_equal(op,"status")&&(oc_equal(fields[3],"settings")||oc_equal(fields[3],"completion")||oc_equal(fields[3],"session")||oc_equal(fields[3],"media")))&&
            !(oc_equal(op,"dismiss")&&oc_equal(fields[3],"usb")))||
           !oc_equal(fields[4],"-")||!oc_equal(fields[5],"-"))goto bad;
    }
    if(!response(200,0))return 1;
    if(oc_equal(op,"status")&&oc_equal(fields[3],"session")) {
        send_text(session_closed(argv[1])?"{\"ok\":true,\"closed\":true}\n":"{\"ok\":true,\"closed\":false}\n");
        return 0;
    }
    if(oc_equal(op,"status")&&oc_equal(fields[3],"media")) { media_offer(argv[1]);return 0; }
    int handled=oc_api_handle(argv[1],fields[1],op,fields[3],fields[4],fields[5]);
    if(handled!=OC_API_FALLBACK)return handled==OC_API_DONE?0:1;
    char *args[]={"sh",argv[2],"api",fields[1],fields[2],fields[3],fields[4],fields[5],0};
#ifdef OC_HOST
    extern char **environ;
    (void)oc_execve("/bin/sh",args,environ);
#else
    char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin","LC_ALL=C",0};
    (void)oc_execve("/bin/sh",args,env);
#endif
    send_text("{\"ok\":false,\"error\":\"backend_unavailable\"}\n");return 1;
bad:
    response(400,"bad_request");return 1;
}
#ifdef OC_HOST
int main(int argc,char **argv) { return run(argc,argv); }
#else
int entry(unsigned *stack) { return run((int)stack[0],(char **)(stack+1)); }
__asm__(".text\n.arm\n.global _start\n.type _start,%function\n_start:\n"
        "mov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
