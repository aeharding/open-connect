/* SPDX-License-Identifier: AGPL-3.0-or-later
 * One entry marker and OEM logging readback. No hooks, threads or constructors.
 * Compiled for the exact one-shot generation; output lives only in tmpfs.
 */
extern unsigned COMMON_Log_LevelGet(void);
extern const char *COMMON_LogLevel_ToString(unsigned);
extern int COMMON_Log_Acceptable(unsigned);
#ifndef OC_GENERATION
#error "A fresh generation nonce is required"
#endif

static long call(long n, long a, long b, long c) {
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r7 __asm__("r7") = n;
    __asm__ volatile("svc 0" : "+r"(r0)
                     : "r"(r1), "r"(r2), "r"(r7) : "memory", "cc");
    return r0;
}
static unsigned append(char *out, unsigned n, const char *s) {
    if (!s) return n;
    for (unsigned i = 0; i < 64 && s[i] && n < 240; ++i) out[n++] = s[i];
    return n;
}
__attribute__((visibility("default"))) int oc_bootstrap_v1(void) {
    char out[256], number[16];
    unsigned pid = (unsigned)call(20, 0, 0, 0), end = 15;
    number[end] = 0;
    do { number[--end] = '0' + pid % 10; pid /= 10; } while (pid && end);
    unsigned n = append(out, 0, "OCGEN_NATIVE|" OC_GENERATION "|pid=");
    n = append(out, n, number + end);
    n = append(out, n, "|level=");
    n = append(out, n, COMMON_LogLevel_ToString(COMMON_Log_LevelGet()));
    n = append(out, n, COMMON_Log_Acceptable(5) ? "|info=1" : "|info=0");
    n = append(out, n, COMMON_Log_Acceptable(3) ? "|warn=1\n" : "|warn=0\n");
    const char *path = "/tmp/oc-generation-" OC_GENERATION ".native";
    long fd = call(5, (long)path, 0xc1, 0600); /* O_WRONLY|O_CREAT|O_EXCL */
    if (fd < 0) return 73;
    unsigned done = 0;
    while (done < n) {
        long count = call(4, fd, (long)(out + done), n - done);
        if (count <= 0) { (void)call(6, fd, 0, 0); return 74; }
        done += (unsigned)count;
    }
    return call(6, fd, 0, 0) == 0 ? 0 : 75;
}
