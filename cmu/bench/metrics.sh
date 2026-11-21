#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Read-only, finite resource samples. Host retains stdout; nothing is installed.
set -eu
export LC_ALL=C
export PATH=/usr/bin:/bin:/usr/sbin:/sbin

seconds=$1 interval=$2 token=$3
shift 3
case "$seconds:$interval:$token" in *[!0-9a-f:]*) exit 64;; esac
test "$seconds" -ge 1 && test "$seconds" -le 600
test "$interval" -ge 1 && test "$interval" -le 30
test "${#token}" -eq 32
test "$(id -u)" = 0
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
     $0=="JCI_SW_VER_PATCH=\"A\""{p++}
     $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
     END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
boot=$(cat /proc/sys/kernel/random/boot_id)
marker() { printf '\nOCM1 %s %s\n' "$token" "$*"; }
file() {
    marker "file $1"
    if test -r "$1"; then
        cat "$1" || printf '\nREAD_FAILED\n'
    else
        printf 'UNAVAILABLE\n'
    fi
}
marker "boot $boot"
start=$(cut -d. -f1 /proc/uptime)
index=0
while :; do
    test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
    before=$(cut -d' ' -f1 /proc/uptime)
    test "$index" -eq 0 || test "$((${before%.*} - start))" -lt "$seconds" || break
    marker "sample $index $before"
    for path in /proc/meminfo /proc/stat /proc/vmstat /proc/diskstats /proc/net/dev; do
        file "$path"
    done
    pids=$(pidof "$@") || pids=
    seen=' '
    for pid in $pids; do
        case "$seen" in *" $pid "*) continue;; esac
        seen="$seen$pid "
        path=/proc/$pid
        test -r "$path/comm" || continue
        name=$(cat "$path/comm") || continue
        selected=0
        for wanted do
            if test "$name" = "$wanted"; then selected=1; break; fi
        done
        test "$selected" -eq 1 || continue
        file "$path/stat"
        file "$path/status"
        file "$path/io"
        # A second identity lets the host reject a process that exited/reused its PID.
        file "$path/stat"
    done
    after=$(cut -d' ' -f1 /proc/uptime)
    marker "end $index $after"
    index=$((index + 1))
    sleep "$interval"
done
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
marker "complete $index"
