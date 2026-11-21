#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# One finite SM process, after Mazda renders XML and before Device Manager reads.
set -eu
umask 077
export LC_ALL=C PATH=/usr/bin:/bin:/usr/sbin:/sbin
D=/tmp/mnt/data_persist/oc-bench-wireless
R=/tmp/oc-bench-wireless
T=/tmp/devmgr_config_edit.xml
sha() { value=$(openssl dgst -sha256 < "$1"); printf '%s\n' "${value##* }"; }
absent() { test ! -e "$1" && test ! -L "$1"; }
test "$(id -u)" = 0
test "$(cat /proc/sys/kernel/random/boot_id)" = "$(cat "$R/boot-id")"
test "$(readlink -f "$R")" = "$R"
test "$(stat -c '%a:%u:%g' "$R")" = 700:0:0
test "$(sha /etc/devmgr_config_master.xml)" = 9f1811e2d9a905ba9060a9c20b8d91c18aaa5c079512e3261b51cf0114fc857b
test "$(sha /jci/scripts/get_board_type.sh)" = 2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da
test -f "$T" && test ! -L "$T" && test "$(readlink -f "$T")" = "$T"
absent "$R/devmgr.original.xml" && absent "$R/devmgr.new.xml" && absent "$R/config-ready"
before=$(sha "$T")
mode=$(stat -c '%a' "$T"); owner=$(stat -c '%u:%g' "$T")
(set -C; cat "$T" > "$R/devmgr.original.xml")
test "$(sha "$R/devmgr.original.xml")" = "$before"
awk -f "$D/wireless-device-config.awk" "$R/devmgr.original.xml" > "$R/devmgr.new.xml"
chmod "$mode" "$R/devmgr.new.xml"
chown "$owner" "$R/devmgr.new.xml"
# Unknown concurrent XML changes are not ours to overwrite.
test "$(sha "$T")" = "$before"
mv "$R/devmgr.new.xml" "$T"
printf '%s\n' "$before" > "$R/devmgr.original.sha256"
sha "$T" > "$R/devmgr.applied.sha256"
(set -C; : > "$R/config-ready")
printf '%s\n' WIRELESS_CAPABILITIES_PREPARED
