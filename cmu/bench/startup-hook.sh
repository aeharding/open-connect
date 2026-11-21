#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Temporary bench instrumentation; the supported OEM stage_1 is empty.
# Never hold up Service Manager, including when the bench payload is absent.
D=/tmp/mnt/data_persist/oc-bench-startup
# Optional experiment data. Leave existing RAM settings untouched on conflict.
# Both choices use identical hook code; only the four-letter data value changes.
set_native_log_level() {
    test -e "$D/native-log-level" || return 0
    test -f "$D/native-log-level" && test ! -L "$D/native-log-level" || return 1
    test "$(wc -c < "$D/native-log-level")" -eq 5 || return 1
    level=$(cat "$D/native-log-level")
    case "$level" in Info|Warn) ;; *) return 1;; esac
    for folder in /tmp/common /tmp/common/log; do
        if test ! -e "$folder" && test ! -L "$folder"; then
            mkdir -m 755 "$folder" || return 1
        fi
        test -d "$folder" && test ! -L "$folder" &&
            test "$(readlink -f "$folder")" = "$folder" || return 1
    done
    file=/tmp/common/log/settings.txt
    stage=/tmp/common/log/.oc-startup-log-settings
    test ! -e "$file" && test ! -L "$file" || return 1
    (set -C; printf 'COMMON_LOG_LEVEL=%s\n' "$level" > "$stage") || return 1
    chmod 644 "$stage" || return 1
    test ! -e "$file" && test ! -L "$file" || return 1
    mv "$stage" "$file"
}
set_native_log_level || echo 'OC bench log choice not applied' >&2
if test -f "$D/startup-launch.sh" && test ! -L "$D/startup-launch.sh"; then
    /usr/bin/setsid /bin/sh "$D/startup-launch.sh" </dev/null >/dev/null 2>&1 &
fi
exit 0
