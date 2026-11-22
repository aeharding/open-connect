#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# The embedded hook verifies the whole package before sourcing this selector.
# Standalone execution retains full verification for older installed hooks.

startup_stamp() {
    local tick idle
    read -r tick idle < /proc/uptime
    printf '%s|%s\n' "$1" "$tick" >> /tmp/open-connect/startup-times
}

boot_load() {
    . "$P/state.sh"
    . "$P/firmware.sh"
    . "$P/access.sh"
    . "$P/transaction.sh"
}

boot_select() {
    D=/tmp/mnt/data_persist/open-connect
    R=/tmp/open-connect
    AUTOSTART=/usr/bin/autostart
    boot_load
    firmware_guard
    private_dir "$D" && record_read || fail invalid_state
    test "$P" = "$D/packages/$R_BACKEND" || fail damaged_package
    if test "$R_PHASE" = active; then
        test "$R_BOOT" != "$(cat /proc/sys/kernel/random/boot_id)" || fail already_selected
    fi
    fast=false
    if test "$R_PHASE" = active && test -s "$D/snapshots/$R_CURRENT/dependencies"; then
        snapshot_read "$R_BASE" || fail originals_changed
        base_nvram=$S_NVRAM
        base_login_ok=true
        access_login_check_loaded || base_login_ok=false
        snapshot_read "$R_CURRENT" || fail invalid_snapshot
        if test "$S_PACKAGE" = "$R_BACKEND"; then
            targets_match_loaded "$R_CURRENT" || fail state_changed
            if test "$S_ACCESS" = true; then test "$base_login_ok" = true || fail state_changed; fi
            boot_dependencies_match "$R_CURRENT" || fail state_changed
            fast=true
            startup_stamp targets_dependencies
        fi
    fi
    if test "$fast" = false; then native_guard; fi
    . "$P/service.sh"
    service_stage boot "$R_BACKEND"
    startup_stamp session_ready
    if test "$fast" = false; then
        if test "$R_PHASE" != purge; then transaction_reconcile; fi
        case "$R_PHASE" in
          removed|purge) P=$runtime; uninstall_cleanup; return 1;;
        esac
        test "$R_PHASE" = active || return 1
        targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
        snapshot_read "$R_BASE" || fail originals_changed
        base_nvram=$S_NVRAM
        snapshot_read "$R_CURRENT" || fail invalid_snapshot
        hex "$S_PACKAGE" 64 && private_dir "$D/packages/$S_PACKAGE" && private_dir "$D/composed/$S_PACKAGE" || fail damaged_feature
        test "$(sha "$D/packages/$S_PACKAGE/files.sha256")" = "$S_PACKAGE" || fail damaged_feature
        startup_stamp targets_dependencies
    fi
    package=$S_PACKAGE; warning=$S_WARNING; touch=$S_TOUCH; mode=$S_META
    pandora=$S_PANDORA; base=$S_BASE; wireless=$S_WIRELESS
boot=$(cat /proc/sys/kernel/random/boot_id)
boot_id "$boot" || fail invalid_boot
test "$R_BOOT" != "$boot" || fail already_selected
# An observed OFF followed by a different kernel and ON is an ignition cycle.
# Initial ON, quick resume and frontend readiness never renew the budget.
if test "$R_OFF" != - && test "$R_OFF" != "$boot" && test "$(cat /sys/class/gpio/ACC_Sense/value)" = 1; then
    R_BUDGET=3
fi
R_OFF=-; R_BOOT=$boot
if test "$R_BUDGET" -gt 0; then R_BUDGET=$((R_BUDGET-1)); selected=true; else selected=false; fi
record_write
startup_stamp budget_committed
if test "$S_ACCESS" = true; then printf '%s\n' "$R_CURRENT" > /tmp/open-connect/access-selected; fi
nvram=$base_nvram
if test "$selected:$touch" = true:1; then nvram=disable; fi
if test "$S_NVRAM" != "$nvram"; then
    after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$touch" "$warning" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" "$pandora" "$base" "$wireless") || fail startup_plan_failed
    transaction_prepare apply "$R_CURRENT" "$after"
    transaction_reconcile
fi
# Observe ACC even in baseline mode so a later genuine ignition cycle can retry.
( exec 9>&-; exec sh "$runtime/ignition.sh" "$boot" ) </dev/null >/dev/null 2>&1 &
test "$selected" = true || exit 1
absent /tmp/open-connect/feature || fail feature_already_present
work=$(mktemp -d /tmp/open-connect/.feature-XXXXXX)
cp "$D/composed/$package/uia.so" "$D/composed/$package/mmui.so" \
    "$D/composed/$package/mmui.xml" "$D/composed/$package/system-app.js" "$work/"
startup_stamp feature_copied
if test "$warning" = 1; then setting=on; else setting=off; fi
service_config "$D/composed/$package/sm-normal-$setting.conf" "$work/sm.conf" "$pandora" "$wireless" || fail service_config_failed
service_config "$D/composed/$package/sm-wcp-$setting.conf" "$work/sm_WCP.conf" "$pandora" "$wireless" || fail service_config_failed
if test "$wireless" = 1; then
    cp "$P/wireless.sh" "$work/wireless.sh"
    cp "$P/wireless-device.awk" "$work/wireless-device.awk"
    printf '%s\n' "$boot" > "$work/boot-id"
    printf '0\n' > "$work/wireless-applied"
fi
token=$(cat "$runtime/token"); hex "$token" 32 || fail invalid_token
sed "s/@TOKEN@/$token/" "$D/composed/$package/index-$setting.html" > "$work/index.html"
mv "$work" /tmp/open-connect/feature
printf '%s\n' "$R_CURRENT" > /tmp/open-connect/selected
# Publish the optional external RAM resource last. A failed atomic link cannot
# overwrite another provider, and must not leave our selected marker claiming it.
if ! native_log_config "$base"; then
    rm /tmp/open-connect/selected
    fail logging_config_failed
fi
startup_stamp selector_exit
return 0
}

boot_main() {
    set -eu
    umask 077
    P=$(dirname "$(readlink -f "$0")")
    D=/tmp/mnt/data_persist/open-connect
    R=/tmp/open-connect
    boot_load
    if absent "$R"; then mkdir -m 700 "$R"; fi
    private_dir "$R" || fail invalid_runtime
    if absent "$R/lock"; then (set -C; : > "$R/lock") || fail invalid_lock; fi
    file "$R/lock" || fail invalid_lock
    exec 9<>"$R/lock"
    flock -n -x 9 || fail busy
    private_dir "$D" && record_read || fail invalid_state
    test "$(sha "$P/files.sha256")" = "$R_BACKEND" && verify_package "$P" || fail damaged_package
    if absent "$R/startup-times"; then : > "$R/startup-times"; fi
    file "$R/startup-times" || fail invalid_runtime
    startup_stamp standalone_verified
    boot_select
}

case "${0##*/}" in boot.sh) boot_main;; esac
