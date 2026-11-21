#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
set -eu
test "$(id -u)" = 0
test "$(cat /proc/sys/kernel/random/boot_id)" = "$1"
test -c /dev/input/event1
test "$(cat /sys/class/input/event1/device/name)" = 'Virtual Keyboard'
awk '{exit !($1>=300)}' /proc/uptime
# These are press/sync/release/sync reports, matching the qualified bench input.
right=AAAAAAAAAAABAGoAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAagAAAAAAAAAAAAAAAAAAAAAAAAAAAA==
left=AAAAAAAAAAABAGkAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAaQAAAAAAAAAAAAAAAAAAAAAAAAAAAA==
printf '%s' "$left" | base64 -d > /dev/input/event1
sleep 1
printf '%s' "$left" | base64 -d > /dev/input/event1
sleep 3
for number in 1 2 3 4 5; do
    for direction in right left; do
        read -r before rest < /proc/uptime
        case "$direction" in right) report=$right;; left) report=$left;; esac
        printf '%s' "$report" | base64 -d > /dev/input/event1
        read -r after rest < /proc/uptime
        printf 'INPUT|%s|%s|%s|%s\n' "$number" "$direction" "$before" "$after"
        sleep 2
    done
done
