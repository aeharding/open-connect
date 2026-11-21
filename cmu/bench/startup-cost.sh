#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Read-only warm-cache attribution after the declared measurement windows.
set -eu
export LC_ALL=C PATH=/usr/bin:/bin:/usr/sbin:/sbin
test "$(id -u)" = 0
test "$#" = 2
case "$1" in ????????-????-????-????-????????????) ;; *) exit 64;; esac
case "$1$2" in *[!a-f0-9-]*) exit 64;; esac
case "$2" in *[!a-f0-9]*) exit 64;; esac
test "${#2}" = 64
test "$(cat /proc/sys/kernel/random/boot_id)" = "$1"
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++} $0=="JCI_SW_VER_PATCH=\"A\""{p++} $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++} END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
P=$(readlink -f /tmp/open-connect/runtime)
D=/tmp/mnt/data_persist/open-connect
AUTOSTART=/usr/bin/autostart
digest=$(openssl dgst -sha256 < "$P/files.sha256")
test "${digest##* }" = "$2"
# Independently verify the runtime before sourcing it.
while read -r digest name extra; do
    test -z "$extra"
    case "$name" in ''|*[!a-zA-Z0-9.-]*) exit 1;; esac
    test -f "$P/$name" && test ! -L "$P/$name"
    actual=$(openssl dgst -sha256 < "$P/$name")
    test "${actual##* }" = "$digest"
done < "$P/files.sha256"
. "$P/state.sh"
. "$P/firmware.sh"
. "$P/access.sh"
. "$P/transaction.sh"
record_read
test "$R_PHASE" = active
measure() {
    label=$1; shift
    read -r before rest < /proc/uptime
    "$@"
    read -r after rest < /proc/uptime
    printf 'CHECK|%s|%s|%s\n' "$label" "$before" "$after"
}
for repeat in 1 2 3; do
    printf 'REPEAT|%s\n' "$repeat"
    measure firmware_guard firmware_guard
    measure native_guard native_guard
    measure persistent_manifest verify_manifest "$D/packages/$R_BACKEND"
    measure runtime_manifest verify_manifest "$P"
    measure target_state targets_match "$R_CURRENT"
    measure dependencies dependencies_match "$R_CURRENT"
    measure base_snapshot snapshot_read "$R_BASE"
    measure current_snapshot snapshot_read "$R_CURRENT"
done
test "$(root_mode)" = ro,noatime
echo WARM_READ_ONLY_PROFILE_COMPLETE
