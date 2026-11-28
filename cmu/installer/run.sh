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
test "$(grep '^JCI_SW_VER=' /jci/version.ini)" = 'JCI_SW_VER="MAZ_CMU-150_74.00.324"' || refuse firmware
test "$(grep '^JCI_SW_VER_PATCH=' /jci/version.ini)" = 'JCI_SW_VER_PATCH="A"' || refuse patch
test "$(grep '^JCI_SW_FLAVOR=' /jci/version.ini)" = 'JCI_SW_FLAVOR="cmu150_NA"' || refuse region
source=$(dirname "$(readlink -f "$0")")
case "$source" in /tmp/mnt/sd[a-d]1/open-connect) ;; *) refuse location;; esac
lock=/tmp/open-connect-usb.lock
if test ! -e "$lock" && test ! -L "$lock"; then (set -C; : > "$lock") 2>/dev/null || :; fi
test -f "$lock" && test ! -L "$lock" && test "$(readlink -f "$lock")" = "$lock" && test "$(stat -c '%u:%g' "$lock")" = "$(id -u):$(id -g)" || refuse lock
exec 8<>"$lock"
flock -n -x 8 || exit 0
work=$(mktemp -d /tmp/oc-usb-XXXXXX)
cleanup() { rm -f "$work"/* "$work"/.[!.]* "$work"/..?*; rmdir "$work"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
test -f "$source/files.sha256" && test ! -L "$source/files.sha256" || refuse manifest
msize=$(stat -c %s "$source/files.sha256") || refuse manifest
case "$msize" in ''|*[!0-9]*) refuse manifest;; esac
test "$msize" -le 65536 || refuse manifest
cp "$source/files.sha256" "$work/files.sha256"
count=0
seen='|files.sha256|'
expected=
set --
# Require complete records and visible names, matching the session consumers.
while read -r digest name extra; do
    test "${#digest}" -eq 64 && test -n "$name" && test -z "$extra" || refuse manifest
    case "$digest" in *[!a-f0-9]*) refuse manifest;; esac
    case "$name" in .*|*[!a-zA-Z0-9.-]*) refuse manifest;; esac
    case "$seen" in *"|$name|"*) refuse duplicate;; esac
    seen="$seen$name|"
    test -f "$source/$name" && test ! -L "$source/$name" || refuse payload
    count=$((count+1)); test "$count" -le 64 || refuse payload_count
    set -- "$@" "$source/$name"
    expected="$expected$digest *$work/$name
"
done < "$work/files.sha256"
test -z "$digest$name$extra" || refuse manifest
test "$count" -gt 0 || refuse payload
sizes=$(stat -c %s "$@") || refuse payload_size
printf '%s\n' "$sizes" | awk -v count="$count" '
    $0!~/^[0-9]+$/ || $0>=2097152 {bad=1}
    END{exit bad || NR!=count}' || refuse payload_size
cp "$@" "$work/"
set --
while read -r digest name extra; do
    set -- "$@" "$work/$name"
done < "$work/files.sha256"
actual=$(openssl dgst -sha256 -r "$@") || refuse checksum
test "$actual" = "${expected%?}" || refuse checksum
test -f "$work/session.sh" && test -f "$work/api" && test -f "$work/flush" && test -f "$work/install" || refuse payload
chmod 600 "$work/files.sha256" "$@"
chmod 700 "$work/api" "$work/flush" "$work/install"
# Release Mazda's update scanner; the session owns the staged files and lock.
trap '' HUP INT TERM
sh "$work/session.sh" "$work" "$source" </dev/null >/dev/null 2>&1 &
trap - EXIT
