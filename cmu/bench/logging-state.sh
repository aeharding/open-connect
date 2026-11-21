#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Read-only exact-v74 common-log state; no running-process write.
set -eu
test "$(id -u)" = 0
test "${1:-}" = "$(cat /proc/sys/kernel/random/boot_id)"
L=/jci/lib/libjcicommon.so
h=$(openssl dgst -sha256 < "$L");test "${h##* }" = 637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d
inode=$(stat -c %i "$L")
for d in /proc/[0-9]*; do
 test -r "$d/maps" && test -r "$d/stat" || continue
 map=$(awk -v inode="$inode" '$2=="r-xp"&&$3=="00000000"&&$5==inode&&$6=="/jci/lib/libjcicommon.so"{print $1}' "$d/maps" 2>/dev/null || :)
 test -n "$map" || continue
 case "$map" in *'
'*) exit 1;;esac
 start=$(awk '{print $22}' "$d/stat")
 base=${map%%-*}
 address=$((0x$base + 0x31ddc))
 values=$(dd if="$d/mem" bs=4 skip=$((address/4)) count=16 2>/dev/null | od -An -tu4)
 test "$(awk '{print $22}' "$d/stat")" = "$start"
 printf 'LOGSTATE|%s|%s|%s|%s|' "${d##*/}" "$start" "$base" "$(cat "$d/comm")"
 printf '%s\n' "$values"
done
printf 'BOOT|';cat /proc/sys/kernel/random/boot_id
