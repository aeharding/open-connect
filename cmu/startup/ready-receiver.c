/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Bounded one-request loopback readiness receiver. No file writes or reboot.
 * ARM syscall ABI: Linux v3.0 arch/arm/include/asm/unistd.h.
 * A caller binds the token to its generation/current boot and owns recovery.
 */
#ifdef OC_HOST
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
static long result(long n) { return n < 0 ? -errno : n; }
static long close_socket(int fd) { return result(close(fd)); }
static long nonblock(int fd) { return result(fcntl(fd, F_SETFL, O_NONBLOCK)); }
static long new_socket(void) { return result(socket(AF_INET, SOCK_STREAM, 0)); }
static long listen_socket(int fd) { return result(listen(fd, 4)); }
static long accept_socket(int fd) { return result(accept(fd, 0, 0)); }
static long receive(int fd, char *b, unsigned n) { return result(read(fd, b, n)); }
static long bind_socket(int fd, unsigned port) {
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET; a.sin_port = htons((unsigned short)port);
    a.sin_addr.s_addr = htonl(0x7f000001);
    return result(bind(fd, (struct sockaddr *)&a, sizeof a));
}
static long readable(int fd, int ms) {
    struct pollfd p = {fd, POLLIN, 0};
    long r = result(poll(&p, 1, ms));
    return r > 0 && !(p.revents & (POLLIN | POLLHUP)) ? -1 : r;
}
static long now(unsigned *ms) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    *ms = (unsigned)t.tv_sec * 1000u + (unsigned)t.tv_nsec / 1000000u;
    return 0;
}
static long output(const char *s, unsigned n) { return result(write(1, s, n)); }
static void response(int fd, const char *s, unsigned n) {
    (void)send(fd, s, n, 0);
}
#else
#if !defined(__arm__) || !defined(__ARM_EABI__)
#error "ARM EABI target required"
#endif
static long call4(long number, long a, long b, long c, long d) {
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r7 __asm__("r7") = number;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r3), "r"(r7) : "memory", "cc");
    return r0;
}
static long close_socket(int fd) { return call4(6, fd, 0, 0, 0); }
static long nonblock(int fd) { return call4(55, fd, 4, 04000, 0); }
static long new_socket(void) { return call4(281, 2, 1, 0, 0); }
static long listen_socket(int fd) { return call4(284, fd, 4, 0, 0); }
static long accept_socket(int fd) { return call4(285, fd, 0, 0, 0); }
static long receive(int fd, char *b, unsigned n) { return call4(3, fd, (long)b, n, 0); }
static long bind_socket(int fd, unsigned port) {
    struct {unsigned short family, port; unsigned address; unsigned char pad[8];}
        a = {2, (unsigned short)((port << 8) | (port >> 8)), 0x0100007f, {0}};
    return call4(282, fd, (long)&a, sizeof a, 0);
}
static long readable(int fd, int ms) {
    struct {int fd; short events, revents;} p = {fd, 1, 0};
    long r = call4(168, (long)&p, 1, ms, 0);
    return r > 0 && !(p.revents & (1 | 16)) ? -1 : r;
}
static long now(unsigned *ms) {
    struct {long seconds, nanoseconds;} t;
    if (call4(263, 1, (long)&t, 0, 0) < 0) return -1;
    *ms = (unsigned)t.seconds * 1000u + (unsigned)t.nanoseconds / 1000000u;
    return 0;
}
static long output(const char *s, unsigned n) { return call4(4, 1, (long)s, n, 0); }
static void response(int fd, const char *s, unsigned n) {
    (void)call4(289, fd, (long)s, n, 0x4040); /* DONTWAIT | NOSIGNAL */
}
#endif

#define EMIT(s) (output(s, sizeof(s) - 1) == (long)(sizeof(s) - 1))
static unsigned number(const char *s) {
    unsigned n = 0;
    if (!*s || *s == '0') return 0;
    for (; *s; ++s) {
        if (*s < '0' || *s > '9' || n > 6553) return 0;
        n = n * 10 + (unsigned)(*s - '0');
    }
    return n;
}
static int token_ok(const char *s) {
    for (unsigned i = 0; i < 69; ++i) {
        char c = s[i];
        if (!c) return 0;
        if (i == 32) { if (c != '.') return 0; }
        else if (i == 41 || i == 46 || i == 51 || i == 56) { if (c != '-') return 0; }
        else if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return 0;
    }
    return s[69] == 0;
}
static int same(const char *a, const char *b, unsigned n) {
    for (unsigned i = 0; i < n; ++i) if (a[i] != b[i]) return 0;
    return 1;
}
/* The whole header must be received; accepting only a prefix can hide failure. */
static int request(const char *b, unsigned n, const char *token) {
    if (n < 87 || !same(b, "GET /", 5) || !same(b + 5, token, 69) ||
        !same(b + 74, " HTTP/1.", 8) || (b[82] != '0' && b[82] != '1') ||
        b[83] != '\r' || b[84] != '\n') return 0;
    for (unsigned i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)b[i];
        if (c != '\r' && c != '\n' && c != '\t' && (c < 32 || c > 126)) return 0;
    }
    return 1;
}
static int run(int argc, char **argv) {
    if (argc != 4 || !token_ok(argv[2])) return 64;
    unsigned port = number(argv[1]), seconds = number(argv[3]), start, current;
    if (port < 1024 || port > 65535 || seconds < 1 || seconds > 180 || now(&start)) return 64;
    long server = new_socket();
    if (server < 0) return 70;
    if (nonblock((int)server) < 0 || bind_socket((int)server, port) < 0 ||
        listen_socket((int)server) < 0 || !EMIT("OCHEALTH|listening\n")) {
        close_socket((int)server); return 71;
    }
    int status = 75;
    for (;;) {
        if (now(&current)) {status = 74; break;}
        unsigned elapsed = current - start;
        if (elapsed >= seconds * 1000u) break;
        int wait = (int)(seconds * 1000u - elapsed);
        if (wait > 200) wait = 200;
        long ready = readable((int)server, wait);
        if (ready < 0) {status = 74; break;}
        if (!ready) continue;
        long client = accept_socket((int)server);
        if (client < 0) continue;
        if (nonblock((int)client) < 0) {close_socket((int)client); continue;}
        char buffer[4096];
        unsigned used = 0, connected = current;
        int complete = 0;
        while (used < sizeof buffer) {
            if (now(&current)) {status = 74; break;}
            if (current - start >= seconds * 1000u || current - connected >= 2000u) break;
            if (readable((int)client, 50) <= 0) continue;
            long n = receive((int)client, buffer + used, sizeof buffer - used);
            if (n <= 0) break;
            used += (unsigned)n;
            for (unsigned i = 3; i < used; ++i) {
                if (same(buffer + i - 3, "\r\n\r\n", 4)) {complete = 1; break;}
            }
            if (complete) break;
        }
        if (status != 74 && complete && !now(&current) &&
            current - start < seconds * 1000u && request(buffer, used, argv[2])) {
            static const char ok[] = "HTTP/1.0 204 No Content\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
            response((int)client, ok, sizeof ok - 1);
            close_socket((int)client);
            status = EMIT("OCHEALTH|ready\n") ? 0 : 74;
            break;
        }
        close_socket((int)client);
        if (status == 74) break;
    }
    close_socket((int)server);
    if (status == 75) (void)EMIT("OCHEALTH|timeout\n");
    return status;
}
#ifdef OC_HOST
int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);
    return run(argc, argv);
}
#else
int entry(unsigned *stack) {return run((int)stack[0], (char **)(stack + 1));}
__asm__(".text\n.global _start\n.type _start,%function\n"
        "_start:\nmov r0,sp\nbic sp,sp,#7\nbl entry\nmov r7,#1\nsvc 0\n");
#endif
