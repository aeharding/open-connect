#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Retrieval only: never launches or changes the observer.
set -eu
export LC_ALL=C PATH=/usr/bin:/bin:/usr/sbin:/sbin
old_boot=$1 metrics_sha=$2 launch_sha=$3 hook_sha=$4
R=/tmp/oc-bench-startup
test "$(id -u)" = 0
boot=$(cat /proc/sys/kernel/random/boot_id)
test "$boot" != "$old_boot"
test "$(readlink -f "$R")" = "$R"
for name in exit metadata trace.raw stderr audio-exit audio-profile audio-stderr; do
    test -f "$R/$name" && test ! -L "$R/$name"
done
test "$(cat "$R/exit")" = 0
test ! -s "$R/stderr"
test "$(cat "$R/audio-exit")" = 0
test ! -s "$R/audio-stderr"
grep -F "AUDIO_PROFILE|silent-ui-v1|$boot|" "$R/audio-profile" >/dev/null
test "$(awk -F '|' '$1=="BOOT"{print $2}' "$R/metadata")" = "$boot"
test "$(awk -F '|' '$1=="METRICS_SHA"{print $2}' "$R/metadata")" = "$metrics_sha"
test "$(awk -F '|' '$1=="LAUNCH_SHA"{print $2}' "$R/metadata")" = "$launch_sha"
test "$(awk -F '|' '$1=="HOOK_SHA"{print $2}' "$R/metadata")" = "$hook_sha"
printf '\nBOOT_TRACE|%s\n' "$boot"
printf 'BOOT_TRACE_SHA|'; openssl dgst -sha256 < "$R/trace.raw"
cat "$R/metadata"
cat "$R/audio-profile"
cat "$R/trace.raw"
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
