#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# One bounded SM process, after VBS and before Device Manager. Nothing is durable.
set -eu
umask 077
export LC_ALL=C PATH=/usr/bin:/bin:/usr/sbin:/sbin
R=/tmp/open-connect/feature
T=/tmp/devmgr_config_edit.xml
sha() { value=$(openssl dgst -sha256 < "$1") || return; printf '%s\n' "${value##* }"; }
absent() { test ! -e "$1" && test ! -L "$1"; }
case "${1:-}" in
    --prepare)
        # No commands with children or XML writes before the supervisor has
        # confirmed this session. The inherited FIFO descriptors never open
        # a new endpoint here; both were opened read/write before launch.
        test "$#" = 2 && test "$2" = "$$"
        printf '%s\n' "$$" >&3
        IFS= read -r -t 12 permission <&4
        test "$permission" = go;;
    '') test "$#" = 0;;
    *) exit 64;;
esac
test "$(id -u)" = 0
test "$(readlink -f "$R")" = "$R"
test "$(stat -c '%a:%u:%g' "$R")" = 700:0:0
test "$(cat /proc/sys/kernel/random/boot_id)" = "$(cat "$R/boot-id")"
absent "$R/wireless-ready"
prepare() (
    # Keep every failure explicit; no partial output authorizes publication.
    test "$(sha /etc/devmgr_config_master.xml)" = 9f1811e2d9a905ba9060a9c20b8d91c18aaa5c079512e3261b51cf0114fc857b || exit 1
    test "$(sha /jci/vbs/modules/libjcimod_eem.so)" = 0160354861d0dddf09f05dc69df95f14be074de706a4d7656166666d587439d9 || exit 1
    test "$(sha /jci/devicemanager/libdevicemanager.so)" = 88d6291d74fe993536ec724064b8ccfbc133b2341282b93cfc7fb2927fbbc563 || exit 1
    test -f "$T" && test ! -L "$T" && test "$(readlink -f "$T")" = "$T" || exit 1
    absent "$R/wireless-original.xml" && absent "$R/wireless-new.xml" || exit 1
    before=$(sha "$T") || exit 1
    identity=$(stat -c '%d:%i:%a:%u:%g' "$T") || exit 1
    mode=$(stat -c '%a' "$T") || exit 1
    owner=$(stat -c '%u:%g' "$T") || exit 1
    (set -C; cat "$T" > "$R/wireless-original.xml") || exit 1
    test "$(sha "$R/wireless-original.xml")" = "$before" || exit 1
    awk -f "$R/wireless-device.awk" "$R/wireless-original.xml" > "$R/wireless-new.xml" || exit 1
    chmod "$mode" "$R/wireless-new.xml" || exit 1
    chown "$owner" "$R/wireless-new.xml" || exit 1
    test -f "$T" && test ! -L "$T" && test "$(readlink -f "$T")" = "$T" || exit 1
    test "$(stat -c '%d:%i:%a:%u:%g' "$T")" = "$identity" && test "$(sha "$T")" = "$before" || exit 1
    mv "$R/wireless-new.xml" "$T" || exit 1
)
if test "${1:-}" = --prepare; then prepare; exit; fi

worker=; worker_done=0; group_ready=0
stop_worker() {
    test "$worker_done" = 0 || return 0
    # $! also closes the signal window between starting and assigning the PID.
    worker=${worker:-${!:-}}
    test -n "$worker" || return 0
    if read -r process_stat 2>/dev/null < "/proc/$worker/stat"; then
        # State, parent, group and session follow the final ')' in proc stat.
        set -- ${process_stat##*) }
        if test "$#" -ge 4 && test "$2" = "$$"; then
            if test "$group_ready" = 1 && test "$3" = "$worker" && test "$4" = "$worker"; then
                kill -9 "-$worker" 2>/dev/null || :
            else
                # Preparation is still gated, even if setsid completes between
                # this identity read and KILL. No publisher can survive it.
                kill -9 "$worker" 2>/dev/null || :
            fi
        fi
    fi
    wait "$worker" 2>/dev/null || :
    worker_done=1
}
applied_policy() {
    test -f "$T" && test ! -L "$T" && test "$(readlink -f "$T")" = "$T" || return 1
    size=$(stat -c %s "$T") || return 1
    case "$size" in ''|*[!0-9]*) return 1;; esac
    test "$size" -le 65536 || return 1
    wifi=0; oob=0; lines=0; cr=$(printf '\r')
    while IFS= read -r line || test -n "$line"; do
        lines=$((lines+1)); test "$lines" -le 512 || return 1
        line=${line%"$cr"}
        case "$line" in
            *bWifiSupport*)
                test "$line" = '<config><name>bWifiSupport</name><value>TRUE</value></config>' || return 1
                wifi=$((wifi+1));;
            *bOOBSupport*)
                test "$line" = '<config><name>bOOBSupport</name><value>TRUE</value></config>' || return 1
                oob=$((oob+1));;
        esac
    done < "$T"
    test "$wifi:$oob" = 1:1
}
finish() {
    trap - EXIT HUP INT TERM
    stop_worker
    # Cancellation can arrive on either side of the atomic XML rename. Report
    # the actual policy released to Device Manager, rather than worker status.
    applied=0
    if applied_policy; then applied=1; fi
    absent "$R/wireless-applied.next" || exit 1
    (set -C; printf '%s\n' "$applied" > "$R/wireless-applied.next") || exit 1
    mv "$R/wireless-applied.next" "$R/wireless-applied" || exit 1
    (set -C; : > "$R/wireless-ready") || exit 1
    exit 0
}
trap finish EXIT
trap 'exit 1' HUP INT TERM
absent "$R/wireless-ack" && absent "$R/wireless-go"
mkfifo "$R/wireless-ack" "$R/wireless-go"
# Linux FIFO read/write opens do not wait for a peer. All later I/O uses the
# inherited descriptors; an absent worker cannot block an endpoint open.
exec 3<>"$R/wireless-ack" 4<>"$R/wireless-go"
# An asynchronous wait is interruptible when BusyBox timeout signals only this
# supervisor PID. The isolated worker group is stopped before readiness.
/bin/sh -c 'exec /bin/busybox setsid /bin/sh "$1" --prepare "$$"' wireless-worker "$0" &
worker=$!
attempt=0; acknowledged=
while test "$attempt" -lt 10; do
    if IFS= read -r -t 1 acknowledged <&3; then break; fi
    attempt=$((attempt+1))
done
test "$acknowledged" = "$worker"
read -r process_stat 2>/dev/null < "/proc/$worker/stat"
set -- ${process_stat##*) }
test "$#" -ge 4 && test "$2:$3:$4" = "$$:$worker:$worker"
# This assignment must precede GO: from here cancellation kills the group.
group_ready=1
printf 'go\n' >&4
wait "$worker" || :
worker_done=1
