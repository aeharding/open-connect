/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Host lookup fault adapter. Call the maintained wrappers through dlopen too,
 * so the fixture covers the exported ABI without requiring OEM inputs.
 */
#include <assert.h>
#include <dlfcn.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

struct Device { int refs, type; } device;
static int sends, releases, get_lookups, deref_lookups, send_lookups;
static void *expected_self, *expected_fd, *expected_event;
static void *get(void *out, const void *self, const void *fd) {
    assert(self==expected_self && fd==expected_fd);
    *(void **)out=device.type ? &device : NULL;
    return out;
}
static void deref(void **out) {
    assert(*out==&device && device.refs==1);
    --device.refs; ++releases; *out=NULL;
}
static void send_event(void *self, const void *event) {
    assert(self==expected_self && event==expected_event); ++sends;
}
void *touch_lookup(void *handle, const char *symbol) {
    assert(handle==(void *)-1);
    const char *missing=getenv("TOUCH_MISSING");
    if(strstr(symbol,"getDevice")) { ++get_lookups; return missing&&!strcmp(missing,"get")?NULL:(void *)get; }
    if(strstr(symbol,"dereference")) { ++deref_lookups; return missing&&!strcmp(missing,"deref")?NULL:(void *)deref; }
    if(strstr(symbol,"4send")) { ++send_lookups; return missing&&!strcmp(missing,"send")?NULL:(void *)send_event; }
    abort();
}
int main(int argc, char **argv) {
    assert(argc==2);
    void *lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL); assert(lib);
    void *(*wrapper)(void *,const void *,const void *)=dlsym(lib,
        "_ZNK3com3jci3cpp7devices9Composite9getDeviceERKNS1_6common1OINS1_2io14FileDescriptorEEE");
    void (*send_wrapper)(void *,const void *)=dlsym(lib,
        "_ZN3com3jci3cpp7devices9Composite7Udevice4sendERK11input_event");
    assert(wrapper && send_wrapper);
    expected_fd=&sends; expected_event=&releases; expected_self=&device;
    const char *missing=getenv("TOUCH_MISSING");
    if(missing) {
        void *out=NULL;
        device.type=3;device.refs=1;
        if(!strcmp(missing,"get")) { wrapper(&out,expected_self,expected_fd); return 41; }
        if(!strcmp(missing,"deref")) { wrapper(&out,expected_self,expected_fd); return 42; }
        if(!strcmp(missing,"send")) { device.type=1;send_wrapper(&device,expected_event); return 43; }
        return 44;
    }
    for(int repeat=0;repeat<2;++repeat) for(int type=0;type<=3;++type) {
        device.type=type;device.refs=1;
        void *out=(void *)1;
        assert(wrapper(&out,expected_self,expected_fd)==&out);
        if(type==3) { assert(out==NULL && device.refs==0); }
        else { assert(out==(type?&device:NULL) && device.refs==1); }
        int before=sends;
        send_wrapper(&device,expected_event);
        assert(sends==before+(type!=3));
    }
    assert(releases==2);assert(sends==6);
    expected_self=NULL;send_wrapper(NULL,expected_event);assert(sends==7);
    assert(get_lookups==1 && deref_lookups==1 && send_lookups==1);
    assert(dlclose(lib)==0);
}
