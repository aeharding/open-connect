#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Command is supplied through argv; stdin carries seven nonce queries, not code.
set -eu
test "$(id -u)" = 0
test "$(cat /proc/sys/kernel/random/boot_id)" = "$1"
printf '\nBOOT_CLOCK_READY|%s\n' "$1"
for index in 0 1 2 3 4 5 6; do
    IFS= read -r token
    case "$token" in ''|*[!0-9a-f]*) exit 64;; esac
    test "${#token}" -eq 32
    test "$(cat /proc/sys/kernel/random/boot_id)" = "$1"
    printf '\nBOOT_CLOCK_REPLY|%s|' "$token"
    cat /proc/uptime
done
test "$(cat /proc/sys/kernel/random/boot_id)" = "$1"
