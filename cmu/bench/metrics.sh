#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Read-only, finite resource samples. Host retains stdout; nothing is installed.
set -eu
export LC_ALL=C
export PATH=/usr/bin:/bin:/usr/sbin:/sbin

seconds=$1 interval=$2 token=$3
shift 3
case "$seconds:$interval" in *[!0-9:]*) exit 64;; esac
case "$token" in ''|*[!0-9a-f]*) exit 64;; esac
test "$seconds" -ge 1 && test "$seconds" -le 600
test "$interval" -ge 1 && test "$interval" -le 30
test "${#token}" -eq 32
test "$#" -gt 0
for name do
    case "$name" in ''|-*|*[!A-Za-z0-9_-]*) exit 64;; esac
    test "${#name}" -le 15
done
test "$(id -u)" = 0
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
     $0=="JCI_SW_VER_PATCH=\"A\""{p++}
     $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
     END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
# One reader avoids forking cat/printf/cut for every file in every sample.
awk -v token="$token" -v seconds="$seconds" -v pause="$interval" -v names="$*" '
function marker(body) { printf "\nOCM1 %s %s\n", token, body }
function one(path, value, status) {
    status = (getline value < path)
    close(path)
    if (status != 1) exit 74
    return value
}
function clock(fields) {
    split(one("/proc/uptime"), fields, " ")
    return fields[1] + 0
}
function file(path, value, status, count) {
    marker("file " path)
    count = 0
    while ((status = (getline value < path)) > 0) { print value; count++ }
    close(path)
    if (status < 0) print "READ_FAILED"
    else if (!count) print "UNAVAILABLE"
}
BEGIN {
    boot = one("/proc/sys/kernel/random/boot_id")
    marker("boot " boot)
    count = split(names, selected, " ")
    for (i = 1; i <= count; i++) wanted[selected[i]] = 1
    started = clock()
    sample_no = 0
    while ((before = clock()) - started < seconds || sample_no == 0) {
        if (one("/proc/sys/kernel/random/boot_id") != boot) exit 75
        marker(sprintf("sample %d %.2f", sample_no, before))
        file("/proc/meminfo")
        file("/proc/stat")
        file("/proc/vmstat")
        file("/proc/diskstats")
        file("/proc/net/dev")
        # Enumerate once, then read comm directly. BusyBox pidof scans much more.
        command = "printf \"%s\\n\" /proc/[0-9]*"
        while ((command | getline path) > 0) {
            status = (getline name < (path "/comm"))
            close(path "/comm")
            if (status != 1 || !(name in wanted)) continue
            file(path "/stat")
            file(path "/status")
            file(path "/io")
            file(path "/stat")
        }
        if (close(command) != 0) exit 77
        marker(sprintf("end %d %.2f", sample_no, clock()))
        fflush()
        sample_no++
        if (system("sleep " pause) != 0) exit 76
    }
    if (one("/proc/sys/kernel/random/boot_id") != boot) exit 75
    marker("complete " sample_no)
}'
