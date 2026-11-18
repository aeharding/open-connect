#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Generic USB entry: validate, copy the entire payload into RAM, launch it.
set -eu
PATH=/sbin:/bin:/usr/sbin:/usr/bin
export PATH
LC_ALL=C
export LC_ALL
umask 077
refuse() { logger -t open-connect "USB refused: $1"; exit 1; }
test "$(id -u)" = 0 || refuse privileges
test "$(grep '^JCI_SW_VER=' /jci/version.ini)" = 'JCI_SW_VER="MAZ_CMU-150_55.00.750"' || refuse firmware
test "$(grep '^JCI_SW_VER_PATCH=' /jci/version.ini)" = 'JCI_SW_VER_PATCH="B"' || refuse patch
test "$(grep '^JCI_SW_FLAVOR=' /jci/version.ini)" = 'JCI_SW_FLAVOR="cmu150_NA"' || refuse region
source=$(dirname "$(readlink -f "$0")")
case "$source" in /tmp/mnt/sd[a-d]1/open-connect) ;; *) refuse location;; esac
lock=/tmp/open-connect-usb.lock
if test ! -e "$lock" && test ! -L "$lock"; then (set -C; : > "$lock") || exit 1; fi
test -f "$lock" && test ! -L "$lock" && test "$(readlink -f "$lock")" = "$lock" || refuse lock
exec 8<>"$lock"
flock -n -x 8 || exit 0
work=$(mktemp -d /tmp/oc-usb-XXXXXX)
cleanup() { rm -f "$work"/*; rmdir "$work"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
test -f "$source/files.sha256" && test ! -L "$source/files.sha256" || refuse manifest
cp "$source/files.sha256" "$work/files.sha256"
count=0
while read -r digest name extra; do
    test "${#digest}" -eq 64 && test -n "$name" && test -z "$extra" || refuse manifest
    case "$digest" in *[!a-f0-9]*) refuse manifest;; esac
    case "$name" in .|..|*[!a-zA-Z0-9.-]*) refuse manifest;; esac
    test ! -e "$work/$name" && test ! -L "$work/$name" || refuse duplicate
    test -f "$source/$name" && test ! -L "$source/$name" || refuse payload
    test "$(stat -c %s "$source/$name")" -lt 2097152 || refuse payload_size
    cp "$source/$name" "$work/$name"
    actual=$(openssl dgst -sha256 < "$work/$name") || refuse checksum
    test "${actual##* }" = "$digest" || refuse checksum
    count=$((count+1)); test "$count" -le 64 || refuse payload_count
done < "$work/files.sha256"
test -f "$work/session.sh" && test -f "$work/api" && test -f "$work/flush" || refuse payload
chmod 700 "$work/api" "$work/flush"
# Release Mazda's update scanner; the session owns the staged files and lock.
sh "$work/session.sh" "$work" "$source" </dev/null >/dev/null 2>&1 &
trap - EXIT
