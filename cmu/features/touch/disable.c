/* SPDX-License-Identifier: AGPL-3.0-or-later */
#include <stddef.h>

/* v74 returns Object<Udevice> through the hidden result slot (r0).
 * The OEM classifier owns the already-open FD. Release ABS devices through
 * Mazda's reference-count operation; retain all other input and SM lifecycle.
 * Lookup failure must reach finite boot recovery, never silently lose input.
 */
#define RTLD_NEXT ((void *)-1)
#define EV_ABS_TYPE 3

extern void *dlsym(void *handle, const char *symbol);

typedef void *(*get_device_fn)(void *out, const void *self, const void *fd);
typedef void (*deref_udev_fn)(void **ptr);
typedef void (*udevice_send_fn)(void *self, const void *ev);

static get_device_fn real_get_device;
static deref_udev_fn real_deref_udev;
static udevice_send_fn real_udevice_send;

static const char SYM_GET_DEVICE[] =
    "_ZNK3com3jci3cpp7devices9Composite9getDeviceERKNS1_6common1OINS1_2io14FileDescriptorEEE";
static const char SYM_DEREF_UDEV[] =
    "_ZN3com3jci3cpp6common6Object11dereferenceINS1_7devices9Composite7UdeviceEEEvRPT_";
static const char SYM_UDEV_SEND[] =
    "_ZN3com3jci3cpp7devices9Composite7Udevice4sendERK11input_event";

__attribute__((visibility("default")))
void *_ZNK3com3jci3cpp7devices9Composite9getDeviceERKNS1_6common1OINS1_2io14FileDescriptorEEE(
    void *out, const void *self, const void *fd)
{
    get_device_fn fn = __atomic_load_n(&real_get_device, __ATOMIC_ACQUIRE);
    if (!fn) {
        fn = (get_device_fn)dlsym(RTLD_NEXT, SYM_GET_DEVICE);
        __atomic_store_n(&real_get_device, fn, __ATOMIC_RELEASE);
    }
    if (!fn) __builtin_trap();
    fn(out, self, fd);
    void *udev = *(void **)out;
    if (udev && *(const int *)((const char *)udev + 4) == EV_ABS_TYPE) {
        deref_udev_fn df = __atomic_load_n(&real_deref_udev, __ATOMIC_ACQUIRE);
        if (!df) {
            df = (deref_udev_fn)dlsym(RTLD_NEXT, SYM_DEREF_UDEV);
            __atomic_store_n(&real_deref_udev, df, __ATOMIC_RELEASE);
        }
        if (!df) __builtin_trap();
        df((void **)out);
    }
    return out;
}

__attribute__((visibility("default")))
void _ZN3com3jci3cpp7devices9Composite7Udevice4sendERK11input_event(
    void *self, const void *ev)
{
    if (self && *(const int *)((const char *)self + 4) == EV_ABS_TYPE) {
        return;
    }
    udevice_send_fn fn = __atomic_load_n(&real_udevice_send, __ATOMIC_ACQUIRE);
    if (!fn) {
        fn = (udevice_send_fn)dlsym(RTLD_NEXT, SYM_UDEV_SEND);
        __atomic_store_n(&real_udevice_send, fn, __ATOMIC_RELEASE);
    }
    if (!fn) __builtin_trap();
    fn(self, ev);
}
