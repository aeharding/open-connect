/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Detached-process bench probe. Load only into the read-only SM client.
 * Standard dynamic imports; no process injection or running-service patch.
 */
extern unsigned COMMON_Log_LevelGet(void);
extern unsigned COMMON_Log_CacheGet(void);
extern unsigned COMMON_Log_EnableGet(void);
static char line[] = "OC_LOG_PROBE|level=0|cache=0|enabled=0\n";
static void put(char *p, unsigned n) {
    register unsigned r0 __asm__("r0") = 1;
    register char *r1 __asm__("r1") = p;
    register unsigned r2 __asm__("r2") = n;
    register unsigned r7 __asm__("r7") = 4;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r7) : "memory");
}
__attribute__((constructor)) static void report(void) {
    line[19] = (char)('0' + COMMON_Log_LevelGet());
    line[27] = (char)('0' + COMMON_Log_CacheGet());
    line[37] = (char)('0' + COMMON_Log_EnableGet());
    put(line, sizeof(line) - 1);
}
