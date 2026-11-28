#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Temporary maintenance endpoint. Never publishes or stops installed Settings.
set -eu
umask 077
P=$(dirname "$(readlink -f "$0")")
R=/tmp/open-connect
D=/tmp/mnt/data_persist/open-connect
. "$P/service.sh"
service_config usb

children() {
    local cmd
    for cmd in /proc/[0-9]*/cmdline; do
        test -r "$cmd" || continue
        if tr '\0' '\n' < "$cmd" | awk -v p="$P/" '
            index($0,p)==1&&$0!=p"usb-service.sh"{found=1}END{exit !found}'; then return 0; fi
    done
    return 1
}

retire() {
    local count=0 path
    case "$P" in "$R"/sessions/session-*) ;; *) return 1;; esac
    private_dir "$P" && file "$P/closed" || return 1
    # A native request may still be reading immutable files after disconnect.
    while children; do
        count=$((count+1)); test "$count" -lt 190 || return 1
        sleep 1
    done
    for path in "$P"/.[!.]* "$P"/..?*; do absent "$path" || return 1; done
    for path in "$P"/*; do
        if test "$path" = "$P/admitted" && test -L "$path"; then continue; fi
        test -f "$path" && test ! -L "$path" || return 1
    done
    rm -f "$P"/*
    rmdir "$P"
}

needed() {
    service_usb_retained "$1"
}

case "${1:-start}" in
retire) retire;;
drain)
    trap 'rm -f "$P/draining"' EXIT
    trap 'exit 1' HUP INT TERM
    count=0
    while test "$count" -lt 130; do
        test "$(readlink -f "$service_runtime" 2>/dev/null || :)" = "$P" || exit 0
        needed "$P" || break
        count=$((count+1))
        sleep 1
    done
    rm -f "$P/draining"
    trap - EXIT
    exec sh "$P/usb-service.sh" stop
    ;;
stop)
    service_lock usb
    : > "$P/closed"
    if test "$(readlink -f "$service_runtime" 2>/dev/null || :)" = "$P"; then
        if needed "$P"; then
            if (set -C; : > "$P/draining") 2>/dev/null; then
                exec 8>&- 9>&-
                sh "$P/usb-service.sh" drain </dev/null >/dev/null 2>&1 &
            fi
            exit 0
        fi
        stop_listener
        rm -f "$service_runtime" "$service_listener"
    fi
    exec 8>&- 9>&-
    # Bounded retirement is independent of the scanner and global write lock.
    sh "$P/usb-service.sh" retire </dev/null >/dev/null 2>&1 &
    ;;
start)
    unpublished=
    trap 'if test -n "$unpublished" && test -d "$unpublished"; then
        : > "$unpublished/closed"
        (exec 8>&- 9>&-; sh "$unpublished/usb-service.sh" retire) </dev/null >/dev/null 2>&1 &
    fi' EXIT
    trap 'exit 1' HUP INT TERM
    service_lock usb
    if absent "$R/sessions"; then mkdir -m 700 "$R/sessions"; fi
    private_dir "$R/sessions" || fail invalid_sessions
    exec 9>&-
    # run.sh already verified this private RAM packet. Hardlinks retain those
    # bytes without a second payload allocation or a long transaction lock.
    runtime=$(
        staged=
        trap 'if test -n "$staged"; then rm -f "$staged"/*; rmdir "$staged"; fi' EXIT
        trap 'exit 1' HUP INT TERM
        package=$(sha "$P/files.sha256") && hex "$package" 64 || fail damaged_runtime
        service_files "$package" usb
        staged=$runtime
        trap - EXIT HUP INT TERM
        printf '%s\n' "$runtime"
    )
    unpublished=$runtime
    service_lock usb
    old=
    if ! absent "$service_runtime"; then old=$(readlink -f "$service_runtime") || fail invalid_runtime_pointer; fi
    if test -n "$old"; then
        case "$old" in "$R"/sessions/session-*) ;; *) fail invalid_runtime_pointer;; esac
        private_dir "$old" || fail invalid_runtime_pointer
        if needed "$old"; then fail operation_pending; fi
        : > "$old/closed"
    fi
    service_listen "$runtime" usb
    unpublished=
    if test -n "$old"; then
        (exec 8>&- 9>&-; sh "$old/usb-service.sh" retire) </dev/null >/dev/null 2>&1 &
    fi
    printf '%s\n' "$runtime"
    ;;
*) fail invalid_action;;
esac
