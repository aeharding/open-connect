#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Temporary maintenance endpoint. Never publishes or stops installed Settings.
# Sourced only by an admitted USB writer, with the operation lock held.
usb_fence() {
    local pointer=/tmp/open-connect/runtime target selected package source digest listener pid start old extra port identity fresh
    absent "$pointer" && return 0
    test -L "$pointer" || fail invalid_legacy_runtime
    target=$(readlink "$pointer") || fail invalid_legacy_runtime
    case "$target" in /tmp/open-connect/sessions/session-*) ;; *) fail invalid_legacy_runtime;; esac
    private_dir "$target" || fail invalid_legacy_runtime
    selected=$(selection_id /tmp/open-connect/selected) || fail invalid_selected_snapshot
    package=$(snapshot_package "$selected") || fail invalid_selected_snapshot
    source=$(package_programs "$package" backend.sh) || fail invalid_legacy_source
    file "$target/files.sha256" && test "$(sha "$target/files.sha256")" = "$package" &&
        file "$target/backend.sh" || fail invalid_legacy_source
    digest=$(sha "$source/backend.sh") || fail invalid_legacy_source
    test "$(sha "$target/backend.sh")" = "$digest" || fail invalid_legacy_source
    # A verified pinned endpoint keeps its public pointer until normal restart.
    if awk '$0=="# Open Connect pinned Settings 1"{n++}END{exit n!=1}' "$source/backend.sh"; then return 0; fi
    # Only the actually supported dev.22 contract is eligible for withdrawal.
    test "$digest" = 518809f76ea2bfe6cbe33387ee1646c607c00dde7e798c22702510285bf89485 &&
        test "$(package_version "$package")" = 0.3.0-dev.22 || fail unsupported_legacy_runtime
    file /tmp/open-connect/listener || fail invalid_listener
    listener=$(cat /tmp/open-connect/listener) || fail invalid_listener
    read -r pid start old extra <<LISTENER
$listener
LISTENER
    test -z "$extra" && test "$old" = "$target" || fail invalid_listener
    port=15555
    service_owns_listener "$pid" "$start" "$target" "$port" || {
        port=35555; service_owns_listener "$pid" "$start" "$target" "$port" || fail listener_replaced
    }
    identity=$(status_identity) || fail state_changed
    # The legacy backend checks this exact pointer after taking our same flock,
    # before reading OC1. Keep its process, port and immutable RAM packet intact.
    if rm "$pointer" && absent "$pointer"; then return 0; fi
    # A failed withdrawal is definitely before prepare. Restore only this exact
    # link with freshly unchanged authority; never replace another publication.
    if absent "$pointer" && fresh=$(status_identity) && test "$fresh" = "$identity" &&
        test "$(cat /tmp/open-connect/listener)" = "$listener" &&
        service_owns_listener "$pid" "$start" "$target" "$port"; then
        ln -s "$target" "$pointer" || :
    fi
    fail legacy_fence_failed
}
if test "${usb_helpers:-false}" = true; then return; fi

set -eu
umask 077
P=$(dirname "$(readlink -f "$0")")
R=/tmp/open-connect
D=/tmp/mnt/data_persist/open-connect
. "$P/state.sh"
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
stop)
    service_lock usb
    : > "$P/closed"
    if test "$(readlink -f "$service_runtime" 2>/dev/null || :)" = "$P"; then
        if needed "$P"; then exit 0; fi
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
        service_files "$(sha "$P/files.sha256")" usb
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
