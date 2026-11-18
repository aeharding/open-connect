#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Start or replace the local service from a verified package. Old session files
# remain until reboot: an already-running request may still map its executable.
set -eu
umask 077
P=$(dirname "$(readlink -f "$0")")
. "$P/state.sh"
R=/tmp/open-connect
if absent "$R"; then mkdir -m 700 "$R"; fi
private_dir "$R" || fail invalid_runtime
if absent "$R/lock"; then : > "$R/lock"; fi
file "$R/lock" || fail invalid_lock
exec 9<>"$R/lock"
count=0
until flock -n -x 9; do
    count=$((count+1)); test "$count" -le 5 || fail busy
    sleep 1
done
# Both callers run from a verified package. Validate the copied bytes below;
# hashing the source again here would duplicate the early boot check.
stop_listener() {
if ! absent "$R/listener"; then
    file "$R/listener" || fail invalid_listener
    read -r pid start old extra < "$R/listener" || fail invalid_listener
    case "$pid:$start" in *[!0-9:]*|:*) fail invalid_listener;; esac
    case "$old" in "$R"/sessions/session-*) ;; *) fail invalid_listener;; esac
    test -z "$extra" || fail invalid_listener
    if test -d "/proc/$pid"; then
        test "$(awk '{print $22}' "/proc/$pid/stat")" = "$start" &&
            test "$(readlink "/proc/$pid/exe")" = /bin/busybox &&
            tr '\0' '\n' < "/proc/$pid/cmdline" | grep -F -q "$old/api" || fail listener_replaced
        kill -TERM "$pid" || fail listener_stop_failed
        count=0
        while test -d "/proc/$pid" && test "$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null)" = "$start"; do
            count=$((count+1)); test "$count" -lt 4 || fail listener_stop_failed
            sleep 1
        done
    fi
fi
}
case "${1:-start}" in
    stop)
        verify_manifest "$P" || fail damaged_package
        test "$(readlink -f "$R/runtime")" = "$P" || exit 0
        absent "$R/selected" || exit 0
        D=/tmp/mnt/data_persist/open-connect
        if ! absent "$D/record"; then
            private_dir "$D" && record_read || fail invalid_record
            test "$R_PHASE" = removed || exit 0
        fi
        stop_listener
        rm "$R/runtime" "$R/listener"
        exit;;
    start) ;;
    *) fail invalid_action;;
esac
if absent "$R/sessions"; then mkdir -m 700 "$R/sessions"; fi
private_dir "$R/sessions" || fail invalid_sessions
work=$(mktemp -d "$R/sessions/session-XXXXXX")
while read -r digest name extra; do
    hex "$digest" 64 && test -n "$name" && test -z "$extra" || fail invalid_manifest
    case "$name" in .|..|*[!a-zA-Z0-9.-]*) fail invalid_manifest;; esac
    file "$P/$name" || fail invalid_source
    cp "$P/$name" "$work/$name"
    chmod 600 "$work/$name"
done < "$P/files.sha256"
cp "$P/files.sha256" "$work/files.sha256"
chmod 600 "$work/files.sha256"
chmod 700 "$work/api" "$work/flush"
verify_manifest "$work" || fail damaged_runtime
# One capability per boot keeps the installed Settings client usable while a
# replacement USB service is staged, even if its UI loading is cancelled.
if absent "$R/token"; then
    uuid > "$R/token.next"
    mv "$R/token.next" "$R/token"
fi
file "$R/token" && test "$(wc -c < "$R/token")" -eq 33 || fail token_failed
token=$(cat "$R/token"); hex "$token" 32 || fail token_failed
cp "$R/token" "$work/token"
stop_listener
if ! absent "$R/runtime"; then test -L "$R/runtime" || fail invalid_runtime_pointer; fi
# This RAM pointer is protected by the operation lock. A missing pointer during
# replacement refuses a request; it never authorizes a persistent operation.
ln -sfn "$work" "$R/runtime"
( exec 8>&- 9>&-; exec /bin/busybox tcpsvd -E -c 4 127.0.0.1 35555 \
    /bin/busybox timeout -t 60 "$work/api" "$work/token" "$work/backend.sh" ) </dev/null >"$work/service.log" 2>&1 &
pid=$!
sleep 1
test -d "/proc/$pid" && test "$(readlink "/proc/$pid/exe")" = /bin/busybox || fail listener_start_failed
start=$(awk '{print $22}' "/proc/$pid/stat")
printf '%s %s %s\n' "$pid" "$start" "$work" > "$R/listener.next"
mv -f "$R/listener.next" "$R/listener"
printf '%s\n' "$work"
