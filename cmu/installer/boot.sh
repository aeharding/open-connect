#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# A successful exit selects one complete RAM configuration. Nothing modifies
# these files during this boot, including update, uninstall or preference writes.
set -eu
umask 077
P=$(dirname "$(readlink -f "$0")")
D=/tmp/mnt/data_persist/open-connect
AUTOSTART=/usr/bin/autostart
. "$P/state.sh"
. "$P/firmware.sh"
. "$P/access.sh"
. "$P/transaction.sh"
firmware_guard
native_guard
private_dir "$D" && record_read || fail invalid_state
test "$(sha "$P/files.sha256")" = "$R_BACKEND" && verify_manifest "$P" || fail damaged_package
runtime=$(sh "$P/service.sh") || fail service_failed
exec 9<>/tmp/open-connect/lock
flock -n -x 9 || fail busy
record_read || fail invalid_record
if test "$R_PHASE" != purge; then transaction_reconcile; fi
case "$R_PHASE" in
    removed|purge)
        # Recovery restored startup. Finish from the already-verified RAM copy
        # before allowing Mazda's original configuration to start.
        P=$runtime
        uninstall_cleanup
        exit 1;;
esac
test "$R_PHASE" = active || exit 1
targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
snapshot_read "$R_CURRENT" || fail invalid_snapshot
package=$S_PACKAGE; warning=$S_WARNING; touch=$S_TOUCH; mode=$S_META
# The current snapshot pins every package/composed file, including manifests;
# dependencies_match above has just checked those exact bytes.
hex "$package" 64 && private_dir "$D/packages/$package" && private_dir "$D/composed/$package" || fail damaged_feature
test "$(sha "$D/packages/$package/files.sha256")" = "$package" || fail damaged_feature
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
if test "$S_ACCESS" = true; then printf '%s\n' "$R_CURRENT" > /tmp/open-connect/access-selected; fi
snapshot_read "$R_BASE" || fail originals_changed
nvram=$S_NVRAM
if test "$selected:$touch" = true:1; then nvram=disable; fi
snapshot_read "$R_CURRENT" || fail invalid_snapshot
if test "$S_NVRAM" != "$nvram"; then
    after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$touch" "$warning" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT") || fail startup_plan_failed
    transaction_prepare apply "$R_CURRENT" "$after"
    transaction_reconcile
fi
# Observe ACC even in baseline mode so a later genuine ignition cycle can retry.
( exec 9>&-; exec sh "$runtime/ignition.sh" "$boot" ) </dev/null >/dev/null 2>&1 &
test "$selected" = true || exit 1
absent /tmp/open-connect/feature || fail feature_already_present
work=$(mktemp -d /tmp/open-connect/.feature-XXXXXX)
for name in uia.so mmui.so mmui.xml system-app.js; do cp "$D/composed/$package/$name" "$work/$name"; done
if test "$warning" = 1; then setting=on; else setting=off; fi
cp "$D/composed/$package/sm-normal-$setting.conf" "$work/sm.conf"
cp "$D/composed/$package/sm-wcp-$setting.conf" "$work/sm_WCP.conf"
token=$(cat "$runtime/token"); hex "$token" 32 || fail invalid_token
sed "s/@TOKEN@/$token/" "$D/composed/$package/index-$setting.html" > "$work/index.html"
mv "$work" /tmp/open-connect/feature
printf '%s\n' "$R_CURRENT" > /tmp/open-connect/selected
exit 0
