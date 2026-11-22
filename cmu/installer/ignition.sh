#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# ACC is a physical input. Persist only a sustained OFF observed after ON in
# this kernel; clear it if QuickStart resumes that same kernel.
set -eu
P=$(dirname "$(readlink -f "$0")")
D=/tmp/mnt/data_persist/open-connect
. "$P/state.sh"
IFS= read -r current_boot < /proc/sys/kernel/random/boot_id || exit 1
boot=${1:-$current_boot}
boot_id "$boot" && test "$current_boot" = "$boot" || exit 1
# One observer per kernel, independent of USB or listener readiness.
if absent /tmp/open-connect/ignition.lock; then (set -C; : > /tmp/open-connect/ignition.lock) || exit 1; fi
file /tmp/open-connect/ignition.lock || exit 1
exec 8<>/tmp/open-connect/ignition.lock
flock -n -x 8 || exit 0
seen_on=false
off_samples=0
recorded=-
while IFS= read -r current_boot < /proc/sys/kernel/random/boot_id && test "$current_boot" = "$boot"; do
    IFS= read -r value < /sys/class/gpio/ACC_Sense/value || exit 1
    case "$value" in
        1) seen_on=true; off_samples=0; wanted=-;;
        0) if test "$seen_on" = false; then sleep 1; continue; fi
           off_samples=$((off_samples+1)); test "$off_samples" -ge 3 || { sleep 1; continue; }
           wanted=$boot;;
        *) exit 1;;
    esac
    if test "$wanted" = "$recorded"; then sleep 1; continue; fi
    if (
        exec 9<>/tmp/open-connect/lock
        flock -n -x 9 || exit 75
        record_read || exit 1
        test "$R_PHASE:$R_BOOT" = "active:$boot" || exit 1
        if test "$R_OFF" != "$wanted"; then R_OFF=$wanted; record_write; fi
    ); then
        recorded=$wanted
    else
        result=$?
        test "$result" = 75 || exit 1
    fi
    sleep 1
done
