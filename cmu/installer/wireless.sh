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
test "$(id -u)" = 0
test "$(readlink -f "$R")" = "$R"
test "$(stat -c '%a:%u:%g' "$R")" = 700:0:0
test "$(cat /proc/sys/kernel/random/boot_id)" = "$(cat "$R/boot-id")"
absent "$R/wireless-ready"
applied=0
finish() {
    trap - EXIT HUP INT TERM
    absent "$R/wireless-applied.next" || exit 1
    (set -C; printf '%s\n' "$applied" > "$R/wireless-applied.next") || exit 1
    mv "$R/wireless-applied.next" "$R/wireless-applied" || exit 1
    (set -C; : > "$R/wireless-ready") || exit 1
    exit 0
}
trap finish EXIT
trap 'exit 1' HUP INT TERM
prepare() (
    trap - EXIT HUP INT TERM
    # This function is tested by an if: ash/sh suppress errexit throughout it.
    # Every failure must therefore exit explicitly before publication.
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
# A failed transformation leaves Mazda's configuration in place. Release its
# ordinary initialization rather than leaving Device Manager waiting for us.
# The EXIT/TERM handler also releases initialization after the process deadline.
# The existing status response distinguishes failure from an applied selection.
if prepare; then applied=1; fi
