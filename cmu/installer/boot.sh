#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# The embedded hook verifies the whole package before sourcing this selector.
# Standalone execution retains full verification for older installed hooks.

# Open Connect locked selector interface 1
startup_stamp() {
    local tick idle
    test "${oc_stamp_count:-0}" -lt 12 || return 0
    if read -r tick idle < /proc/uptime; then
        oc_times="${oc_times-}$1|$tick
"
        oc_stamp_count=$((${oc_stamp_count:-0}+1))
    fi
    return 0
}

startup_stamps_publish() {
    # First bounded receipt only. Never open a pre-existing diagnostic path.
    local receipt
    if test -e /tmp/open-connect/startup-times || test -L /tmp/open-connect/startup-times; then return 0; fi
    receipt=$(mktemp /tmp/open-connect/.startup-times-XXXXXX) || return 0
    printf '%s' "${oc_times-}" > "$receipt" || :
    "$runtime/flush" l "$receipt" /tmp/open-connect/startup-times 2>/dev/null || :
    rm -f "$receipt" || :
    return 0
}

boot_load() {
    . "$P/state.sh"
    . "$P/firmware.sh"
    . "$P/access.sh"
    . "$P/transaction.sh"
}

boot_copy_package() {
    local destination=$1 name expected
    shift
    for name in "$@"; do
        expected=$(awk -v name="$name" '$2==name{n++;print $1}END{exit n!=1}' "$P/files.sha256") || return 1
        hex "$expected" 64 && cp "$P/$name" "$destination/$name" &&
            test "$(sha "$destination/$name")" = "$expected" || return 1
    done
}

boot_observer_stage() {
    absent "$R/ignition" || fail observer_already_present
    observer=$(mktemp -d "$R/.ignition-XXXXXX") || fail observer_create_failed
    boot_copy_package "$observer" ignition.sh state.sh flush || fail observer_copy_failed
    chmod 600 "$observer/ignition.sh" "$observer/state.sh" && chmod 700 "$observer/flush" || fail observer_mode_failed
    runtime=$observer
}

boot_plan_verify() {
    local snapshot=$1 mode=$2 magic base backend dir=$D/snapshots/$1
    snapshot_verify "$snapshot" && file "$dir/boot.plan" &&
        awk '$2=="boot.plan"{n++}END{exit n!=1}' "$dir/files.sha256" || return 1
    IFS='|' read -r magic base backend < "$dir/boot.plan" || return 1
    test "$magic:$base:$backend" = "OCBP1:$R_BASE:$R_BACKEND" || return 1
    "$P/boot-select" "$mode" / "${dir#/}" < "$dir/boot.plan"
}

boot_select() {
    D=/tmp/mnt/data_persist/open-connect
    R=/tmp/open-connect
    AUTOSTART=/usr/bin/autostart
    boot_load
    firmware_guard
    boot_mount_guard || fail invalid_boot_mounts
    test "$(root_mode)" = ro,noatime || fail root_mount_changed
    absent "$R/feature" && absent "$R/selected" || fail already_selected
    private_dir "$D" && record_read || fail invalid_state
    reseal_before=$R_CURRENT
    test "$P" = "$D/packages/$R_BACKEND" || fail damaged_package
    if test "$R_PHASE" = active; then
        test "$R_BOOT" != "$(cat /proc/sys/kernel/random/boot_id)" || fail already_selected
    fi
    fast=false
    if test "$R_PHASE" = active; then
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
    modern=${oc_outer_observer:-false}
    if test "$modern:$fast" = true:true; then
        # Ordinary verified fallback stages only the observer; SM owns Settings.
        boot_observer_stage
    else
        . "$P/service.sh"
        service_files "$R_BACKEND"
    fi
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
    if test "$modern" = true && test -z "${observer:-}"; then boot_observer_stage; fi
    hinted=false
    if file "$D/reseal" && test "$(stat -c '%a:%u:%g' "$D/reseal")" = "600:$(id -u):$(id -g)" &&
        test "$(wc -c < "$D/reseal")" -eq 65 && test "$(cat "$D/reseal")" = "$R_CURRENT"; then
        boot_plan_verify "$R_CURRENT" recheck || fail reseal_inputs_changed
        hinted=true
    fi
    if test "${S_SELECTOR_RECORDED:-false}" = true || test "$hinted" = true; then
        # Re-attest unchanged bytes after ordinary inode drift. Fold the new
        # snapshot into the imminent budget commit, never a second authority.
        R_CURRENT=$(boot_snapshot_seal "$R_CURRENT") || fail boot_snapshot_failed
        snapshot_read "$R_CURRENT" || fail invalid_snapshot
    fi
    package=$S_PACKAGE; warning=$S_WARNING; touch=$S_TOUCH; mode=$S_META
    prefs=$S_PREFS; base=$S_BASE; wireless=$S_WIRELESS
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
if file "$D/reseal" && test "$(stat -c '%a:%u:%g' "$D/reseal")" = "600:$(id -u):$(id -g)" &&
    test "$(wc -c < "$D/reseal")" -eq 65 && test "$(cat "$D/reseal")" = "$reseal_before"; then
    # Only after verified resealing and the durable record commit. This request
    # never replaces OC1 or grants permission to activate a changed input.
    rm "$D/reseal" && flush d "$D" || fail reseal_hint_cleanup_failed
fi
startup_stamp budget_committed
if test "$S_ACCESS" = true; then printf '%s\n' "$R_CURRENT" > /tmp/open-connect/access-selected; fi
nvram=$base_nvram
if test "$selected:$touch" = true:1; then nvram=disable; fi
if test "$S_NVRAM" != "$nvram"; then
    after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" "$prefs") || fail startup_plan_failed
    transaction_prepare apply "$R_CURRENT" "$after"
    transaction_reconcile
fi
# Modern autostart launches the verified observer outside its timeout, on both
# valid outcomes. Legacy installed hooks retain their standalone behavior.
if test "$modern" = true; then
    absent "$R/ignition" && mv "$observer" "$R/ignition" || fail observer_publish_failed
    runtime=$R/ignition
else
    ( exec 9>&-; exec sh "$runtime/ignition.sh" "$boot" ) </dev/null >/dev/null 2>&1 &
fi
if test "$selected" != true; then
    if test "$modern" = true; then return 2; else return 1; fi
fi
absent /tmp/open-connect/feature || fail feature_already_present
work=$(mktemp -d /tmp/open-connect/.feature-XXXXXX)
if test "$warning" = 1; then
    cp "$D/composed/$package/mmui.so" "$D/composed/$package/mmui.xml" "$work/"
    if ! absent "$D/snapshots/$R_CURRENT/boot.plan"; then
        boot_plan_verify "$R_CURRENT" verify || fail feature_inputs_changed
        for name in uia.so system-app.js; do
            ln -s "../../mnt/data_persist/open-connect/composed/$package/$name" "$work/$name" || fail feature_link_failed
        done
    else
        # Older unsealed snapshots retain their original RAM-copy path.
        cp "$D/composed/$package/uia.so" "$D/composed/$package/system-app.js" "$work/" || fail feature_copy_failed
    fi
fi
startup_stamp feature_copied
if test "$warning" = 1; then setting=on; else setting=off; fi
cp "$D/snapshots/$R_CURRENT/sm-normal.conf" "$work/sm.conf" &&
    cp "$D/snapshots/$R_CURRENT/sm-wcp.conf" "$work/sm_WCP.conf" || fail service_config_failed

if test "$wireless" = 1; then
    cp "$P/wireless.sh" "$work/wireless.sh"
    cp "$P/wireless-device.awk" "$work/wireless-device.awk"
    printf '%s\n' "$boot" > "$work/boot-id"
    printf '0\n' > "$work/wireless-applied"
fi
if absent "$R/token"; then
    token=$(uuid); hex "$token" 32 || fail invalid_token
    (set -C; printf '%s\n' "$token" > "$R/token") || fail invalid_token
fi
file "$R/token" && test "$(wc -c < "$R/token")" -eq 33 || fail invalid_token
token=$(cat "$R/token"); hex "$token" 32 || fail invalid_token
boot_copy_package "$work" runtime.js dialog.js settings.js service.sh || fail feature_ui_failed
version=$(cat "$P/VERSION")
case "$version" in ''|*[!a-zA-Z0-9.-]*) fail invalid_version;; esac
sed -e "s/@TOKEN@/$token/" -e "s/@VERSION@/$version/" -e "s/@NOTICE@/$R_NOTICE/" \
    "$D/composed/$package/index-$setting.html" > "$work/index.html"
mv "$work" /tmp/open-connect/feature
# Preparation can be cancelled. Keep it in this shell, not a detached mutation.
boot_cancelled=false; LOG_STAGE=
trap 'boot_cancelled=true' HUP INT TERM
if ! native_log_prepare "$base"; then
    native_log_discard || :
    fail logging_config_failed
fi
if test "$boot_cancelled" = true; then
    native_log_discard || :
    fail selection_cancelled
fi
marker=$(mktemp /tmp/open-connect/.selected-XXXXXX) || fail selection_marker_failed
printf '%s\n' "$R_CURRENT" > "$marker" || fail selection_marker_failed
# Only RAM link/publication syscalls remain. Finish this short commit despite
# TERM, or return stock after removing our exact logging inode. Never hash or
# launch an unbounded worker in this signal-protected section.
trap '' HUP INT TERM
if test "$boot_cancelled" = true; then
    rm -f "$marker" || :
    native_log_discard || :
    fail selection_cancelled
fi
if ! native_log_commit "$runtime/flush" || ! "$runtime/flush" l "$marker" /tmp/open-connect/selected; then
    rm -f "$marker" || :
    native_log_discard || :
    fail selection_commit_failed
fi
rm -f "$marker" || :
if test -n "$LOG_STAGE"; then rm -f "$LOG_STAGE" || :; LOG_STAGE=; fi
startup_stamp selector_exit
return 0
}

boot_main() {
    # This bootstrap cannot call package libraries: older installed hooks exec
    # this entry. Keep verification independent until the lock and hashes pass.
    entry=$(dirname "$(readlink -f "$0")")
set -eu
umask 077
read -r entered idle < /proc/uptime || entered=unknown
test "$(id -u)" = 0
D=/tmp/mnt/data_persist/open-connect
R=/tmp/open-connect
test "$(readlink -f "$D")" = "$D"
test "$(stat -c '%a:%u:%g' "$D")" = 700:0:0
if test ! -e "$R" && test ! -L "$R"; then mkdir -m 700 "$R"; fi
test "$(readlink -f "$R")" = "$R"
test "$(stat -c '%a:%u:%g' "$R")" = 700:0:0
if test ! -e "$R/lock" && test ! -L "$R/lock"; then (set -C; : > "$R/lock"); fi
test -f "$R/lock" && test ! -L "$R/lock" || exit 1
exec 9<>"$R/lock"
flock -n -x 9
test -f "$D/record" && test ! -L "$D/record" || exit 1
test "$(wc -l < "$D/record")" -eq 1
IFS="|" read -r format phase rev package rest < "$D/record"
test "$format" = OC1 && test "${#package}" -eq 64 || exit 1
case "$package" in *[!a-f0-9]*) exit 1;; esac
P=$D/packages/$package
test "$P" = "$entry" || exit 1
test "$(readlink -f "$P")" = "$P"
test -f "$P/files.sha256" && test ! -L "$P/files.sha256" || exit 1
digest=$(openssl dgst -sha256 < "$P/files.sha256")
test "${digest##* }" = "$package"
expected=; seen='|'; mandatory=0; count=0
set --
while read -r digest name extra; do
    test "${#digest}" = 64 && test -n "$name" && test -z "$extra" || exit 1
    case "$digest" in *[!a-f0-9]*) exit 1;; esac
    case "$name" in .|..|*[!a-zA-Z0-9.-]*) exit 1;; esac
    case "$seen" in *"|$name|"*) exit 1;; esac
    seen="$seen$name|"
    case "$name" in boot.sh|state.sh|firmware.sh|access.sh|transaction.sh|service.sh) mandatory=$((mandatory+1));; esac
    test -f "$P/$name" && test ! -L "$P/$name" || exit 1
    set -- "$@" "$P/$name"
    expected="$expected$digest *$P/$name
"
    count=$((count+1)); test "$count" -le 64
done < "$P/files.sha256"
test "$mandatory" = 6
actual_count=0
for item in "$P"/* "$P"/.[!.]* "$P"/..?*; do
    if test ! -e "$item" && test ! -L "$item"; then continue; fi
    test -f "$item" && test ! -L "$item" || exit 1
    actual_count=$((actual_count+1))
done
test "$actual_count" -eq "$((count+1))"
actual=$(openssl dgst -sha256 -r "$@")
test "$actual" = "${expected%?}" || { printf 'damaged_package\n' >&2; exit 1; }
    oc_times=; oc_stamp_count=0
    startup_stamp standalone_verified
    boot_select
    startup_stamps_publish
}

case "${0##*/}" in boot.sh) boot_main;; esac
