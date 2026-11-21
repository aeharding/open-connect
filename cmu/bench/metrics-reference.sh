#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Playground control: two resource endpoints with no interval collector.
set -eu
export LC_ALL=C
token=$1 seconds=$2
test "$(id -u)" = 0
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
     $0=="JCI_SW_VER_PATCH=\"A\""{p++}
     $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
     END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
boot=$(cat /proc/sys/kernel/random/boot_id)
snapshot() {
    printf '\nREF %s %s %s\n' "$token" "$1" "$boot"
    cat /proc/uptime
    sed -n '1p' /proc/stat
    sed -n '/^MemFree:/p' /proc/meminfo
}
snapshot START
sleep "$seconds"
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
snapshot END
