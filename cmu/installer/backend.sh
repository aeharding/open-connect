#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
set -eu
umask 077
export LC_ALL=C
P=$(dirname "$(readlink -f "$0")")
D=/tmp/mnt/data_persist/open-connect
AUTOSTART=/usr/bin/autostart
. "$P/state.sh"
. "$P/firmware.sh"
. "$P/transaction.sh"

# Errors are fixed identifiers, never device output or interpolated user text.
fail() { printf '{"ok":false,"error":"%s"}\n' "$1"; exit 1; }
firmware_guard
private_dir /tmp/open-connect || fail runtime_unavailable
file /tmp/open-connect/lock || fail invalid_lock
exec 9<>/tmp/open-connect/lock
flock -n -x 9 || fail busy
test "$(readlink -f /tmp/open-connect/runtime)" = "$P" || fail session_replaced
test "${1:-}" = api && test "$#" -eq 6 || fail invalid_request
revision=$2; operation=$3; argument=$4; expected=$5; desired=$6

exists=false
empty_state=false
removed_now=false
if ! absent "$D"; then
    private_dir "$D" || fail invalid_state_directory
    if ! absent "$D/record"; then
        record_read || fail invalid_record; exists=true
    else
        empty_state=true
        for path in "$D"/* "$D"/.[!.]* "$D"/..?*; do
            absent "$path" || empty_state=false
        done
    fi
fi

status() {
    local installed=false retained=false conflict=false touch=0 warning=0 notice=- rev=- restart=$removed_now pending=false
    if test "$exists" = false && test -e /tmp/open-connect/selected; then restart=true; fi
    if test "$empty_state" = true; then pending=true; fi
    if test "$exists" = true; then
        record_read || fail invalid_record
        rev=$R_CURRENT; notice=$R_NOTICE
        if test "$R_PHASE" = purge; then
            rev=$R_REV; restart=true; pending=true
        else
            snapshot_read "$R_CURRENT" || fail invalid_snapshot
            touch=$S_TOUCH; warning=$S_WARNING
            if test "$R_PHASE" = active; then installed=true; fi
            if test "$R_PHASE" = removed; then retained=true; fi
            if ! targets_match "$R_CURRENT" || ! dependencies_match "$R_CURRENT"; then conflict=true; fi
            if test "$R_PHASE" = active; then
                if ! file /tmp/open-connect/selected || test "$(cat /tmp/open-connect/selected)" != "$R_CURRENT"; then restart=true; fi
            elif test -e /tmp/open-connect/selected; then restart=true; fi
            if ! settled; then restart=true; pending=true; rev=$R_REV; fi
        fi
    fi
    local version
    version=$(cat "$P/VERSION")
    case "$version" in ''|*[!a-zA-Z0-9.-]*) fail invalid_version;; esac
    # Keep the retired boolean false for an installed v0.2.0-dev.1 client during
    # USB handoff. No endpoint or UI offers Undo.
    printf '{"ok":true,"revision":"%s","installed":%s,"retained":%s,"undo":false,"conflict":%s,"restart":%s,"pending":%s,"touch":%s,"warning":%s,"notice":"%s","version":"%s"}\n' \
        "$rev" "$installed" "$retained" "$conflict" "$restart" "$pending" "$touch" "$warning" "$notice" "$version"
}

finish_removal() {
    uninstall_cleanup
    exists=false; empty_state=false; removed_now=true
}

if test "$operation" = status; then status; exit; fi
if test "$exists" = true; then
    # UI comparisons bind the affected state. ACC and dismissed notices do not
    # invalidate an otherwise-current preference page. Pending work uses its
    # unique record revision instead.
    current_revision=$R_CURRENT
    settled || current_revision=$R_REV
    test "$revision" = "$current_revision" || fail stale_state
    if ! settled; then
        test "$operation" = recover || fail operation_pending
        if test "$R_PHASE" != purge; then transaction_reconcile; fi
        case "$R_PHASE" in removed|purge) finish_removal;; esac
        status; exit
    fi
else
    test "$revision" = - || fail stale_state
fi
case "$operation" in
    install|set|uninstall) test "$(root_mode)" = ro,noatime || fail root_mount_changed;;
esac

case "$operation" in
recover)
    if test "$empty_state" = true; then finish_removal; fi
    ;;
install)
    test "$(root_mode)" = ro,noatime || fail root_mount_changed
    if test "$exists" = true && test "$R_PHASE" = active; then
        targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    fi
    stock_dependencies || fail unsupported_original
    if absent "$D"; then mkdir -m 700 "$D" || fail state_create_failed; flush d /tmp/mnt/data_persist; fi
    for path in snapshots packages composed; do
        if absent "$D/$path"; then mkdir -m 700 "$D/$path" || fail state_create_failed; fi
        private_dir "$D/$path" || fail invalid_state_directory
    done
    flush d "$D"
    originals_save
    old_package=-; touch=1; warning=1
    if test "$exists" = true && test "$R_PHASE" = active; then
        snapshot_read "$R_CURRENT" || fail invalid_snapshot
        old_package=$S_PACKAGE; touch=$S_TOUCH; warning=$S_WARNING
        before=$(state_capture "$old_package" "$touch" "$warning") || fail checkpoint_failed
    else
        test "$(sha "$AUTOSTART")" = "$(sha "$D/originals/autostart")" || fail unsupported_startup
        before=$(state_capture - 0 0) || fail checkpoint_failed
        R_BASE=$before
    fi
    package=$(package_save) || fail package_failed
    compose "$package" >/dev/null || fail composition_failed
    snapshot_read "$R_BASE" || fail originals_changed
    nvram=$S_NVRAM; mode=$S_META
    test "$touch" = 0 || nvram=disable
    deps=$(mktemp "$D/.dependencies-XXXXXX")
    dependencies_capture "$package" > "$deps" || fail checkpoint_dependencies_failed
    after=$(snapshot_create "$D/composed/$package/autostart" "$package" "$touch" "$warning" "$nvram" "$mode" "$deps") || fail plan_failed
    rm "$deps"
    R_BACKEND=$package
    if test "$exists" = false; then
        R_PHASE=removed; R_CURRENT=$before; R_BEFORE=-; R_AFTER=-
        R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-
        record_write; exists=true
    fi
    transaction_prepare install "$before" "$after"
    transaction_reconcile
    ;;
set)
    test "$exists" = true && test "$R_PHASE" = active || fail not_installed
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    snapshot_read "$R_CURRENT" || fail invalid_snapshot
    package=$S_PACKAGE; touch=$S_TOUCH; warning=$S_WARNING; mode=$S_META
    case "$argument:$expected:$desired" in
        touch:[01]:[01]) test "$touch" = "$expected" || fail stale_setting; touch=$desired;;
        warning:[01]:[01]) test "$warning" = "$expected" || fail stale_setting; warning=$desired;;
        *) fail invalid_setting;;
    esac
    if test "$expected" = "$desired"; then status; exit; fi
    snapshot_read "$R_BASE" || fail originals_changed
    nvram=$S_NVRAM; test "$touch" = 0 || nvram=disable
    after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$touch" "$warning" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies") || fail plan_failed
    transaction_prepare set "$R_CURRENT" "$after"
    transaction_reconcile
    ;;
uninstall)
    test "$exists" = true || fail not_installed
    # Removed v0.2.0-dev.1 installations can discard their retained files too.
    if test "$R_PHASE" = removed; then finish_removal; status; exit; fi
    test "$R_PHASE" = active || fail not_installed
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    uninstall_owned "$R_CURRENT" || fail state_changed
    snapshot_read "$R_CURRENT" || fail invalid_snapshot
    before=$(state_capture "$S_PACKAGE" "$S_TOUCH" "$S_WARNING") || fail checkpoint_failed
    snapshot_read "$R_BASE" || fail originals_changed
    after=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - 0 0 "$S_NVRAM" "$S_META" "$D/snapshots/$before/dependencies") || fail plan_failed
    transaction_prepare uninstall "$before" "$after"
    transaction_reconcile
    finish_removal
    ;;
dismiss)
    if test "$exists" = true; then R_NOTICE=-; record_write; fi
    : > "$P/closed"
    ;;
restart)
    if test "$exists" = true; then
        settled || fail operation_pending
        targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    else
        # A completed uninstall has removed its record along with all backups.
        absent "$D" || fail operation_pending
    fi
    test "$(root_mode)" = ro,noatime || fail root_mount_changed
    # A restart explicitly requested for this newly committed configuration is
    # already covered by its finite budget. This endpoint never replenishes it.
    status
    ( exec 9>&-; sleep 2; /sbin/reboot ) </dev/null >/dev/null 2>&1 &
    exit
    ;;
*) fail invalid_request;;
esac
status
