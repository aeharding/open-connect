/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Run a program in a private mount namespace. No mount or exec follows a failed
 * unshare. Linux v3.0 ARM EABI; no target libc or BusyBox unshare dependency.
 * The caller supplies a deadline and validates the program and its inputs.
 */
#ifdef OC_TEST
long oc_syscall(long number, long a, long b, long c, long d, long e);
#else
#if !defined(__arm__) || !defined(__ARM_EABI__)
#error "Target build requires 32-bit ARM EABI"
#endif
static long oc_syscall(long number, long a, long b, long c, long d, long e) {
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e;
    register long r7 __asm__("r7") = number;
    __asm__ volatile("svc 0" : "+r"(r0)
                     : "r"(r1), "r"(r2), "r"(r3), "r"(r4), "r"(r7)
                     : "memory", "cc");
    return r0;
}
#endif

static void report(const char *text, unsigned length) {
    (void)oc_syscall(4, 2, (long)text, length, 0, 0);
}
#define SAY(s) report(s, sizeof(s) - 1)
static int failure(long result) {
    return result < 0 && result >= -125 ? (int)-result : 125;
}

static int run(int argc, char **argv, char **envp) {
    if (argc < 2 || argv[1][0] != '/') {
        SAY("usage: namespace /absolute/program [arguments]\n");
        return 64;
    }
    long result = oc_syscall(337, 0x00020000, 0, 0, 0, 0); /* CLONE_NEWNS */
    if (result != 0) {
        SAY("OCNS|unshare|failed\n");
        return failure(result);
    }
    /* Stop both directions of mount propagation before the program can mount. */
    result = oc_syscall(21, 0, (long)"/", 0, 0x40000 | 0x4000, 0);
    if (result != 0) {
        SAY("OCNS|private_mounts|failed\n");
        return failure(result);
    }
    SAY("OCNS|isolated\n");
    result = oc_syscall(11, (long)argv[1], (long)(argv + 1), (long)envp, 0, 0);
    SAY("OCNS|exec|failed\n");
    return failure(result);
}

#ifndef OC_TEST
int entry(unsigned *stack) {
    int argc = (int)stack[0];
    char **argv = (char **)(stack + 1);
    return run(argc, argv, argv + argc + 1);
}
__asm__(".text\n.global _start\n.type _start,%function\n"
        "_start:\nmov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
