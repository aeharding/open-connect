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
. "$P/access.sh"
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

selection_id() {
    local value
    file "$1" && test "$(wc -c < "$1")" -eq 65 && test "$(wc -l < "$1")" -eq 1 &&
        IFS= read -r value < "$1" && hex "$value" 64 || return 1
    printf '%s\n' "$value"
}

status() {
    local installed=false retained=false conflict=false touch=0 warning=0 notice=- rev=- restart=$removed_now pending=false
    local developer=false uart=0 owner_ssh=0 key=- fingerprint=- uart_current=0 ssh_current=0 wireless_current=0
    local installed_version=- installed_package=- pandora= base= wireless= autoshow= autoshow_current=0
    local saved_schema= saved_config= saved_catalog= selected_services= selected_wireless=0 rows=
    local selected= access_selected= version_hash= completion_check=false audited=false kernel_boot=
    selected=$(selection_id /tmp/open-connect/selected) || selected=
    access_selected=$(selection_id /tmp/open-connect/access-selected) || access_selected=
    if test "$exists" = false && test -e /tmp/open-connect/selected; then restart=true; fi
    if test "$empty_state" = true; then pending=true; fi
    if test "$exists" = true; then
        record_read || fail invalid_record
        rev=$R_CURRENT; notice=$R_NOTICE
        if test "$R_PHASE" = purge; then
            rev=$R_REV; restart=true; pending=true
        else
            snapshot_read "$R_CURRENT" || fail invalid_snapshot
            installed_package=$S_PACKAGE
            touch=$S_TOUCH; warning=$S_WARNING
            saved_schema=$S_SCHEMA
            if test "$S_SCHEMA" != stock; then
                pandora=$S_PANDORA; base=$S_BASE; wireless=$S_WIRELESS
            fi
            if test "$S_SCHEMA" = OC2; then
                case "$S_PREFS" in *'
carplay-autoshow='*) autoshow=$S_AUTOSHOW;; esac
                saved_config=$D/snapshots/$R_CURRENT/config
                saved_catalog=$S_CATALOG
            fi
            developer=$S_ACCESS; uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
            if test "$key" != - && access_key_verify "$key"; then
                fingerprint=$(/usr/bin/ssh-keygen -l -f "$D/keys/$key.cmu" | awk '{print $2}')
                case "$fingerprint" in *[!a-f0-9:]|'') fingerprint=-;; esac
            fi
            if test "$R_PHASE" = active; then installed=true; fi
            if test "$R_PHASE" = removed; then retained=true; fi
            # Settings reads authenticate saved data, not every OEM flash file.
            # Default USB status and every mutating endpoint retain full checks.
            # A completion notice still promises fresh conflict detection, even
            # when Settings wins the race with the boot-completion status read.
            if test "$installed" = true && test "$notice" = installed && test "$selected" = "$R_CURRENT" &&
                kernel_boot=$(completion_boot_id) &&
                test "$R_BOOT" = "$kernel_boot"; then completion_check=true; fi
            if test "$operation:$argument" != status:settings || test "$completion_check" = true; then
                if ! targets_match_loaded "$R_CURRENT" ||
                    { test "$S_ACCESS" = true && ! access_login_check; } ||
                    ! dependencies_match "$R_CURRENT"; then conflict=true; else audited=true; fi
            fi
            # Authenticate VERSION even on the lightweight read. P may be newer
            # maintenance media; its version is not the installed version.
            if test "$installed" = true && test "$conflict" = false && test "$installed_package" != - &&
                file "$D/packages/$installed_package/VERSION" &&
                { test "$saved_schema" = OC2 || { file "$D/packages/$installed_package/files.sha256" &&
                    test "$(sha "$D/packages/$installed_package/files.sha256")" = "$installed_package"; }; }; then
                version_hash=$(awk '$2=="VERSION"{n++;v=$1}END{if(n!=1)exit 1;print v}' "$D/packages/$installed_package/files.sha256") || version_hash=-
                if test "$(sha "$D/packages/$installed_package/VERSION")" = "$version_hash"; then
                    installed_version=$(cat "$D/packages/$installed_package/VERSION") || installed_version=-
                fi
                case "$installed_version" in ''|*[!a-zA-Z0-9.-]*) installed_version=-;; esac
            fi
            if test "$R_PHASE" = active; then
                if test "$selected" != "$R_CURRENT"; then restart=true; fi
            elif test -e /tmp/open-connect/selected; then restart=true; fi
            if ! settled; then restart=true; pending=true; rev=$R_REV; fi
            # Reuse the current decode, then read each distinct applied ID once.
            if test "$access_selected" = "$R_CURRENT"; then uart_current=$uart; ssh_current=$owner_ssh; fi
            if test "$selected" = "$R_CURRENT"; then
                selected_services=$S_SERVICES; selected_wireless=$S_WIRELESS; autoshow_current=$S_AUTOSHOW
            elif test -n "$selected" && snapshot_read "$selected"; then
                selected_services=$S_SERVICES; selected_wireless=$S_WIRELESS; autoshow_current=$S_AUTOSHOW
                if test "$access_selected" = "$selected"; then uart_current=$S_UART; ssh_current=$S_SSH; fi
            fi
            if test -n "$access_selected" && test "$access_selected" != "$R_CURRENT" && test "$access_selected" != "$selected"; then
                if snapshot_read "$access_selected"; then uart_current=$S_UART; ssh_current=$S_SSH; fi
            fi
        fi
    fi
    local version service_status= wireless_factory=false completion_ready=false
    if test -n "$pandora"; then service_status=',"pandora":'$pandora; fi
    if test -n "$base"; then service_status=$service_status',"base":'$base; fi
    if test -n "$wireless"; then service_status=$service_status',"wireless":'$wireless; fi
    if test -n "$wireless"; then
        if factory_wireless; then wireless_factory=true; fi
        # Wireless also requires its separate runtime application evidence.
        if test "$selected_wireless" = 1 && file /tmp/open-connect/feature/wireless-applied &&
            test "$(cat /tmp/open-connect/feature/wireless-applied)" = 1; then wireless_current=1; fi
        service_status=$service_status',"wirelessCurrent":'$wireless_current',"wirelessFactory":'$wireless_factory
        test "$wireless" = "$wireless_current" || restart=true
    fi
    if test "$saved_schema" = OC2; then
        rows=$(awk -v operation=rows -v catalog="$saved_catalog/services.tsv" -v catalog_bytes="$(wc -c < "$saved_catalog/services.tsv")" -v input="$saved_config" \
            -v input_bytes="$(wc -c < "$saved_config")" -v selected_services="$selected_services" \
            -f "$saved_catalog/preferences.awk") || fail invalid_services_status
        service_status=$service_status',"services":'$rows
    fi
    if test -n "$autoshow"; then
        service_status=$service_status',"carplayAutoshow":'$autoshow',"carplayAutoshowCurrent":'$autoshow_current
        test "$autoshow" = "$autoshow_current" || restart=true
    fi
    version=$(cat "$P/VERSION")
    case "$version" in ''|*[!a-zA-Z0-9.-]*) fail invalid_version;; esac
    if test "$installed" = true && test "$installed_version" != - && test "$pending" = false && test "$conflict" = false &&
        test "$restart" = false && test "$notice" = installed &&
        test "$audited:$completion_check" = true:true &&
        test "$R_BOOT" = "$kernel_boot"; then completion_ready=true; fi
    # Keep the retired boolean false for an installed v0.2.0-dev.1 client during
    # USB handoff. No endpoint or UI offers Undo.
    printf '{"ok":true,"revision":"%s","installed":%s,"retained":%s,"undo":false,"conflict":%s,"restart":%s,"pending":%s,"touch":%s,"warning":%s,"notice":"%s","version":"%s","installedVersion":"%s","developer":%s,"uart":%s,"ssh":%s,"key":"%s","fingerprint":"%s","uartCurrent":%s,"sshCurrent":%s%s}\n' \
        "$rev" "$installed" "$retained" "$conflict" "$restart" "$pending" "$touch" "$warning" "$notice" "$version" \
        "$installed_version" "$developer" "$uart" "$owner_ssh" "$key" "$fingerprint" "$uart_current" "$ssh_current" "$service_status,\"completionReady\":$completion_ready"
}

completion_boot_id() {
    # New maintenance media may serve a still-running pre-marker installation.
    # Only absence permits the legacy proof; malformed markers fail closed.
    if absent /tmp/open-connect/boot-id; then
        local value
        value=$(cat /proc/sys/kernel/random/boot_id) && boot_id "$value" || return 1
        printf '%s\n' "$value"
    else current_boot_id; fi
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
    install|set|import|uninstall) test "$(root_mode)" = ro,noatime || fail root_mount_changed;;
esac

case "$operation" in
recover)
    if test "$empty_state" = true; then finish_removal; fi
    ;;
install)
    # Installation needs the complete maintenance bundle, not the boot listener's
    # smaller verified RAM closure. Refuse before any persistent operation.
    verify_manifest "$P" || fail incomplete_maintenance_bundle
    test "$(root_mode)" = ro,noatime || fail root_mount_changed
    if test "$exists" = true && test "$R_PHASE" = active; then
        targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    fi
    stock_dependencies || fail unsupported_original
    if absent "$D"; then mkdir -m 700 "$D" || fail state_create_failed; flush d /tmp/mnt/data_persist; fi
    for path in snapshots packages composed keys; do
        if absent "$D/$path"; then mkdir -m 700 "$D/$path" || fail state_create_failed; fi
        private_dir "$D/$path" || fail invalid_state_directory
    done
    flush d "$D"
    originals_save
    old_package=-; prefs=; uart=0; owner_ssh=0; key=-
    access_work=$(mktemp -d "$D/.access-XXXXXX") || fail access_plan_failed
    trap 'rm -rf "$access_work"' EXIT
    if test "$exists" = true && test "$R_PHASE" = active; then
        snapshot_read "$R_CURRENT" || fail invalid_snapshot
        test "$S_SCHEMA" = OC2 || test "$S_SCHEMA" = dev9 || fail unsupported_snapshot
        old_package=$S_PACKAGE; prefs=$S_PREFS
        uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
        if test "$S_ACCESS" = true && test "$S_LOGIN_INODE" = -; then fail developer_reinstall_required; fi
        if test "$S_ACCESS" = false; then
            test "$(sha /usr/bin/runlogin)" = b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8 || fail unsupported_console
            absent "/usr/bin/.open-connect-runlogin-$(stat -c %i /usr/bin/runlogin)" || fail console_hold_conflict
        fi
        if test "$S_LOGIN_INODE" = -; then login_inode=$(stat -c %i /usr/bin/runlogin); else login_inode=$S_LOGIN_INODE; fi
        access_capture "$access_work" "$uart" "$owner_ssh" "$key" "$login_inode" || fail access_backup_failed
        selector_capture "$access_work" || fail selector_backup_failed
        before=$(state_capture "$old_package" "$access_work" "$prefs") || fail checkpoint_failed
        snapshot_read "$R_BASE" || fail originals_changed
        if test "$S_ACCESS" = false; then
            R_BASE=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - "$S_NVRAM" "$S_META" "$D/snapshots/$R_BASE/dependencies" "$access_work" "") || fail access_backup_failed
        fi
    else
        test "$(sha "$AUTOSTART")" = "$(sha "$D/originals/autostart")" || fail unsupported_startup
        test "$(sha /usr/bin/runlogin)" = b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8 || fail unsupported_console
        absent "/usr/bin/.open-connect-runlogin-$(stat -c %i /usr/bin/runlogin)" || fail console_hold_conflict
        access_capture "$access_work" 0 0 - || fail access_backup_failed
        selector_capture "$access_work" || fail selector_backup_failed
        before=$(state_capture - "$access_work" "") || fail checkpoint_failed
        R_BASE=$before
    fi
    if test -n "$prefs" && test "$(preference_value "$prefs" base)" = 1; then native_log_inputs_verify || fail base_inputs_changed; fi
    package=$(package_save) || fail package_failed
    compose "$package" >/dev/null || fail composition_failed
    access_compose "$access_work" "$uart" "$owner_ssh" "$key" || fail access_plan_failed
    selector_compose "$access_work" "$package" || fail selector_plan_failed
    snapshot_read "$R_BASE" || fail originals_changed
    nvram=$S_NVRAM; mode=$S_META
    if test -z "$prefs" || test "$(preference_value "$prefs" touch)" = 1; then nvram=disable; fi
    deps=$(mktemp "$D/.dependencies-XXXXXX")
    dependencies_capture "$package" > "$deps" || fail checkpoint_dependencies_failed
    after=$(snapshot_create "$D/composed/$package/autostart" "$package" "$nvram" "$mode" "$deps" "$access_work" "$prefs") || fail plan_failed
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
set|import)
    test "$exists" = true && test "$R_PHASE" = active || fail not_installed
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    snapshot_read "$R_CURRENT" || fail invalid_snapshot
    package=$S_PACKAGE; prefs=$S_PREFS; schema=$S_SCHEMA; mode=$S_META
    test "$schema" = OC2 || test "$schema" = dev9 || fail unsupported_snapshot
    uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
    access_source=$D/snapshots/$R_CURRENT
    if test "$operation" = import || test "$argument" = uart || test "$argument" = ssh; then
        test "$S_ACCESS" = true || fail developer_update_required
        test "$S_LOGIN_INODE" != - || fail developer_reinstall_required
        access_work=$(mktemp -d "$D/.access-XXXXXX") || fail access_plan_failed
        trap 'rm -rf "$access_work"' EXIT
        if test "$operation" = import; then
            test "$argument:$expected:$desired" = -:-:- || fail invalid_request
            key=$(access_key_import) || fail public_key_import_failed
        else
            case "$expected:$desired" in [01]:[01]) ;; *) fail invalid_setting;; esac
            case "$argument" in
                uart) test "$uart" = "$expected" || fail stale_setting; uart=$desired;;
                ssh) test "$owner_ssh" = "$expected" || fail stale_setting; owner_ssh=$desired;;
            esac
        fi
        access_compose "$access_work" "$uart" "$owner_ssh" "$key" || fail access_plan_failed
        selector_keep "$D/snapshots/$R_CURRENT" "$access_work" || fail selector_plan_failed
        access_source=$access_work
    else
        case "$expected:$desired" in [01]:[01]) ;; *) fail invalid_setting;; esac
        case "$argument" in
            touch|warning|base|wireless|carplay-autoshow) preference_key=$argument;;
            *) preference_key=service.$argument;;
        esac
        actual=$(preference_value "$prefs" "$preference_key") || fail invalid_setting
        test "$actual" = "$expected" || fail stale_setting
        prefs=$(preferences_change "$prefs" "$package" "$preference_key" "$desired" "$schema") || fail invalid_setting
    fi
    if test "$operation" = set && test "$expected" = "$desired"; then status; exit; fi
    if test "$(preference_value "$prefs" base)" = 1; then native_log_inputs_verify || fail base_inputs_changed; fi
    touch=$(preference_value "$prefs" touch) || fail invalid_preferences
    snapshot_read "$R_BASE" || fail originals_changed
    nvram=$S_NVRAM; test "$touch" = 0 || nvram=disable
    after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies" "$access_source" "$prefs") || fail plan_failed
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
    # Targets/dependencies and ownership already match this authenticated state.
    # Reserializing an older schema would change its ID and break recovery's
    # deliberate R_BEFORE == R_CURRENT ownership check.
    before=$R_CURRENT
    selector_recorded=$S_SELECTOR_RECORDED
    snapshot_read "$R_BASE" || fail originals_changed
    resources=$D/snapshots/$R_BASE
    if test "$selector_recorded" = true && test "$S_SELECTOR_RECORDED" = false; then
        # An upgrade can retain a dev.8 baseline. Keep the new helper's known
        # original absence explicit through removed/purge cleanup as well.
        resources=$(mktemp -d "$D/.access-XXXXXX") || fail selector_plan_failed
        trap 'rm -rf "$resources"' EXIT
        if test "$S_ACCESS" = true; then
            for name in access runlogin sshd.conf; do cp "$D/snapshots/$R_BASE/$name" "$resources/$name" || fail selector_plan_failed; done
        fi
        printf '%s\n' - > "$resources/selector"
    fi
    after=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - "$S_NVRAM" "$S_META" "$D/snapshots/$before/dependencies" "$resources" "") || fail plan_failed
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
