/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Disposable-process query of Mazda's native logging policy. No service hooks.
 * Preload into a short-lived utility, never into an existing Mazda service.
 */
extern unsigned COMMON_Log_LevelGet(void);
extern const char *COMMON_LogLevel_ToString(unsigned);
extern int COMMON_Log_Acceptable(unsigned);

static long call(long n, long a, long b, long c) {
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r7 __asm__("r7") = n;
    __asm__ volatile("svc 0" : "+r"(r0)
                     : "r"(r1), "r"(r2), "r"(r7) : "memory", "cc");
    return r0;
}
static void out(const char *s) {
    unsigned n = 0;
    while (n < 64 && s[n]) ++n;
    (void)call(4, 1, (long)s, n);
}
static void sample(void) {
    out("OCLOGQUERY|CURRENT|");
    out(COMMON_LogLevel_ToString(COMMON_Log_LevelGet()));
    out("\n");
    for (unsigned i = 0; i < 8; ++i) {
        out("OCLOGQUERY|ALLOWED|");
        out(COMMON_LogLevel_ToString(i));
        out(COMMON_Log_Acceptable(i) ? "|1\n" : "|0\n");
    }
}
__attribute__((constructor)) static void query(void) {
    sample();
    long duration[2] = {2, 0};
    (void)call(162, (long)duration, 0, 0); /* nanosleep */
    sample();
}
