/* SPDX-License-Identifier: AGPL-3.0-or-later
 * One bounded POST request on stdin/stdout, launched by BusyBox tcpsvd.
 * The shell backend owns transactions. No paths or shell source come from HTTP.
 */
#ifdef OC_HOST
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
static long input(char *b, unsigned n) { long r=read(0,b,n); return r<0?-errno:r; }
static long output(const char *b, unsigned n) { long r=write(1,b,n); return r<0?-errno:r; }
static long token_read(const char *p, char *b, unsigned n) {
    int f=open(p,O_RDONLY|O_NOFOLLOW); if(f<0)return -1;
    long r=read(f,b,n); close(f); return r;
}
static void execute(char **args, char **env) { execve("/bin/sh",args,env); }
#else
static long call3(long number,long a,long b,long c) {
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    register long r7 __asm__("r7")=number;
    __asm__ volatile("svc 0":"+r"(r0):"r"(r1),"r"(r2),"r"(r7):"memory","cc");
    return r0;
}
static long input(char *b,unsigned n) { return call3(3,0,(long)b,n); }
static long output(const char *b,unsigned n) { return call3(4,1,(long)b,n); }
static long token_read(const char *p,char *b,unsigned n) {
    long f=call3(5,(long)p,0100000,0); if(f<0)return -1;
    long r=call3(3,f,(long)b,n); (void)call3(6,f,0,0); return r;
}
static void execute(char **args,char **env) { (void)call3(11,(long)"/bin/sh",(long)args,(long)env); }
#endif

static unsigned length(const char *s) { unsigned n=0; while(s[n])n++; return n; }
static int equal(const char *a,const char *b) {
    while(*a&&*a==*b){a++;b++;} return *a==*b;
}
static int lower(int c) { return c>='A'&&c<='Z'?c+32:c; }
static int header(const char *a,const char *b) {
    while(*b&&lower(*a)==*b){a++;b++;} return !*b;
}
static int hexn(const char *s,unsigned n) {
    for(unsigned i=0;i<n;i++)
        if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return 0;
    return !s[n];
}
static int send_text(const char *s) {
    unsigned n=length(s);
    while(n){long r=output(s,n); if(r==-4)continue; if(r<=0)return 0; s+=r;n-=(unsigned)r;}
    return 1;
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
    if(argc!=3||argv[1][0]!='/'||argv[2][0]!='/')return 64;
    char bytes[4097], token[34]; unsigned used=0, boundary=0, size=0;
    while(!boundary){
        if(used==4096){response(400,"headers_too_large");return 1;}
        long n=input(bytes+used,4096-used);
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
                if(!equal(line,"POST /control HTTP/1.1")&&!equal(line,"POST /control HTTP/1.0"))goto bad;
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
                if(!equal(p,"text/plain")&&!equal(p,"text/plain;charset=UTF-8")&&
                   !equal(p,"text/plain; charset=UTF-8"))goto bad;
            }else if(header(line,"transfer-encoding:")||header(line,"expect:"))goto bad;
            line=bytes+i+2; i++;
        }else if(!bytes[i]||((unsigned char)bytes[i]<32&&bytes[i]!='\t'))goto bad;
    }
    if(lengths!=1||types!=1||size<43||boundary+size>4096||used>boundary+size)goto bad;
    while(used<boundary+size){
        long n=input(bytes+used,boundary+size-used);
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
    if(count!=6||!fields[5][0]||!hexn(fields[0],32)||
       (!equal(fields[1],"-")&&!hexn(fields[1],32)&&!hexn(fields[1],64)))goto bad;
    if(token_read(argv[1],token,sizeof token)!=33||token[32]!='\n')return response(403,"unauthorized"),1;
    token[32]=0;
    if(!equal(token,fields[0]))return response(403,"unauthorized"),1;
    const char *op=fields[2];
    if(equal(op,"set")){
        if((!equal(fields[3],"touch")&&!equal(fields[3],"warning"))||
           (!equal(fields[4],"0")&&!equal(fields[4],"1"))||
           (!equal(fields[5],"0")&&!equal(fields[5],"1")))goto bad;
    }else{
        if(!equal(op,"status")&&!equal(op,"install")&&!equal(op,"uninstall")&&
           !equal(op,"undo")&&!equal(op,"restart")&&!equal(op,"dismiss")&&!equal(op,"recover"))goto bad;
        if(!equal(fields[4],"-")||!equal(fields[5],"-")||
           (!equal(fields[3],"-")&&!(equal(op,"uninstall")&&equal(fields[3],"confirm"))))goto bad;
    }
    if(!response(200,0))return 1;
    char *args[]={"sh",argv[2],"api",fields[1],fields[2],fields[3],fields[4],fields[5],0};
    char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin","LC_ALL=C",0};
    execute(args,env);
    send_text("{\"ok\":false,\"error\":\"backend_unavailable\"}\n");return 1;
bad:
    response(400,"bad_request");return 1;
}
#ifdef OC_HOST
int main(int argc,char **argv) { return run(argc,argv); }
#else
int entry(unsigned *stack) { return run((int)stack[0],(char **)(stack+1)); }
__asm__(".text\n.global _start\n.type _start,%function\n_start:\n"
        "mov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
