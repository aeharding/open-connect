#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# USB preview only: validate before staging in RAM. Never remount or install.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
LC_ALL=C
export LC_ALL
umask 077

refuse() { logger -t open-connect "USB preview refused: $1"; exit 1; }
test "$(id -u)" = 0 || refuse privileges
test "$(grep '^JCI_SW_VER=' /jci/version.ini)" = 'JCI_SW_VER="MAZ_CMU-150_55.00.750"' || refuse firmware
test "$(grep '^JCI_SW_VER_PATCH=' /jci/version.ini)" = 'JCI_SW_VER_PATCH="B"' || refuse patch
test "$(grep '^JCI_SW_FLAVOR=' /jci/version.ini)" = 'JCI_SW_FLAVOR="cmu150_NA"' || refuse region
test "$(md5sum < /jci/gui/index.html)" = '0ad187b787e242953a9a7612f55bfcfb  -' || refuse frontend
test "$(md5sum < /jci/gui/framework/js/GuiFramework.js)" = 'e90530cdb9b05922bdcaade8757ea1f9  -' || refuse framework

source=$(dirname "$(readlink -f "$0")")
case "$source" in /tmp/mnt/sd[a-d]1/open-connect) ;; *) refuse location ;; esac
lock=/tmp/open-connect-usb.lock
mkdir "$lock" 2>/dev/null || exit 0
work=
cleanup() {
    if test -n "$work"; then
        rm -f "$work/loader.js" "$work/dialog.js" "$work/usb-preview.js" "$work/session.sh" "$work/receiver" "$work/receiver.log" "$work/payload.sha256"
        rmdir "$work"
    fi
    rmdir "$lock"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
work=$(mktemp -d /tmp/oc-usb-XXXXXX)
test -f "$source/payload.sha256" && test ! -L "$source/payload.sha256" || refuse manifest
cp "$source/payload.sha256" "$work/payload.sha256"
test "$(wc -l < "$work/payload.sha256")" -eq 5 || refuse manifest
for file in loader.js dialog.js usb-preview.js session.sh receiver; do
    test -f "$source/$file" && test ! -L "$source/$file" || refuse payload
    cp "$source/$file" "$work/$file"
    expected=$(awk -v name="$file" '$2==name && NF==2 {n++; hash=$1} END {if(n!=1)exit 1;print hash}' "$work/payload.sha256") || refuse manifest
    test "${#expected}" -eq 64 || refuse manifest
    case "$expected" in *[!a-f0-9]*) refuse manifest ;; esac
    # Hash the staged bytes, not a file that could disappear with the USB drive.
    actual=$(openssl dgst -sha256 < "$work/$file") || refuse checksum
    test "${actual##* }" = "$expected" || refuse checksum
done
chmod 700 "$work/receiver"
token=$(tr -d '-' < /proc/sys/kernel/random/uuid).$(cat /proc/sys/kernel/random/boot_id)
logger -t open-connect "OCUSB|$token|start"
# Release Mazda's update scanner immediately; the staged session owns cleanup.
cd "$work"
sh "$work/session.sh" "$work" "$source" "$token" </dev/null >/dev/null 2>&1 &
trap - EXIT
