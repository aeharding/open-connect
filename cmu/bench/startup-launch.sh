#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Finite local boot observer. Only the installation lives on flash; output is RAM.
set -eu
umask 077
export LC_ALL=C PATH=/usr/bin:/bin:/usr/sbin:/sbin
D=/tmp/mnt/data_persist/oc-bench-startup
R=/tmp/oc-bench-startup
test "$(id -u)" = 0
test "$(readlink -f "$D")" = "$D"
test "$(stat -c '%a:%u:%g' "$D")" = 700:0:0
# A boot-local claim prevents duplicate collectors and accidental trace overwrite.
mkdir "$R"
ulimit -f 8192
boot=$(cat /proc/sys/kernel/random/boot_id)
token=$(printf '%s' "$boot" | tr -d -)
test "${#token}" = 32
sha() { value=$(openssl dgst -sha256 < "$1"); printf '%s\n' "${value##* }"; }
expected=$(awk '$2=="metrics.sh"{print $1}' "$D/files.sha256")
test "${#expected}" = 64
test "$(sha "$D/metrics.sh")" = "$expected"
{
    printf 'BOOT|%s\nMETRICS_SHA|%s\nLAUNCH_SHA|%s\n' "$boot" "$expected" "$(sha "$D/startup-launch.sh")"
    printf 'HOOK_SHA|%s\nSTART_UPTIME|' "$(sha /jci/scripts/stage_1.sh)"
    cat /proc/uptime
} > "$R/metadata"
set +e
timeout -t 190 sh "$D/metrics.sh" 180 1 "$token" > "$R/trace.raw" 2> "$R/stderr"
code=$?
set -e
printf '%s\n' "$code" > "$R/exit.tmp"
mv "$R/exit.tmp" "$R/exit"
exit "$code"
