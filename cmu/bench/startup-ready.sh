#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Read-only readiness query; do not mistake a surviving old boot for the restart.
set -eu
test "$(id -u)" = 0
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
     $0=="JCI_SW_VER_PATCH=\"A\""{p++}
     $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
     END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
boot=$(cat /proc/sys/kernel/random/boot_id)
test "$boot" != "$1"
printf '\nSTARTUP_READY|%s|%s|' "$2" "$boot"
cat /proc/uptime
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
