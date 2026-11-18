#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# ACC is a physical input. Persist only a sustained OFF observed after ON in
# this kernel; clear it if QuickStart resumes that same kernel.
set -eu
P=$(dirname "$(readlink -f "$0")")
D=/tmp/mnt/data_persist/open-connect
. "$P/state.sh"
boot=$1
boot_id "$boot" && test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot" || exit 1
seen_on=false
off_samples=0
recorded=-
while test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"; do
    value=$(cat /sys/class/gpio/ACC_Sense/value) || exit 1
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
        test "$R_PHASE" = active || exit 0
        if test "$R_OFF" != "$wanted"; then R_OFF=$wanted; record_write; fi
    ); then
        recorded=$wanted
    else
        result=$?
        test "$result" = 75 || exit 1
    fi
    sleep 1
done
