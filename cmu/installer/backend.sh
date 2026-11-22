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

status() {
    local installed=false retained=false conflict=false touch=0 warning=0 notice=- rev=- restart=$removed_now pending=false
    local developer=false uart=0 owner_ssh=0 key=- fingerprint=- uart_current=0 ssh_current=0 wireless_current=0 applied
    local installed_version=- installed_package=- pandora= base= wireless=
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
            if test "$S_CONFIG_FIELDS" -ge 6; then pandora=$S_PANDORA; fi
            if test "$S_CONFIG_FIELDS" -ge 7; then base=$S_BASE; fi
            if test "$S_CONFIG_FIELDS" -ge 8; then wireless=$S_WIRELESS; fi
            developer=$S_ACCESS; uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
            if test "$key" != - && access_key_verify "$key"; then
                fingerprint=$(/usr/bin/ssh-keygen -l -f "$D/keys/$key.cmu" | awk '{print $2}')
                case "$fingerprint" in *[!a-f0-9:]|'') fingerprint=-;; esac
            fi
            if test "$R_PHASE" = active; then installed=true; fi
            if test "$R_PHASE" = removed; then retained=true; fi
            if ! targets_match "$R_CURRENT" || ! dependencies_match "$R_CURRENT"; then conflict=true; fi
            # The verified dependencies pin the installed package's VERSION.
            # P may instead be a newer client staged from maintenance media.
            if test "$installed" = true && test "$conflict" = false && test "$installed_package" != - &&
                file "$D/packages/$installed_package/VERSION"; then
                installed_version=$(cat "$D/packages/$installed_package/VERSION") || installed_version=-
                case "$installed_version" in ''|*[!a-zA-Z0-9.-]*) installed_version=-;; esac
            fi
            if test "$R_PHASE" = active; then
                if ! file /tmp/open-connect/selected || test "$(cat /tmp/open-connect/selected)" != "$R_CURRENT"; then restart=true; fi
            elif test -e /tmp/open-connect/selected; then restart=true; fi
            if ! settled; then restart=true; pending=true; rev=$R_REV; fi
            if file /tmp/open-connect/access-selected; then
                applied=$(cat /tmp/open-connect/access-selected)
                if snapshot_read "$applied"; then uart_current=$S_UART; ssh_current=$S_SSH; fi
            fi
        fi
    fi
    local version service_status= wireless_factory=false
    if test -n "$pandora"; then service_status=',"pandora":'$pandora; fi
    if test -n "$base"; then service_status=$service_status',"base":'$base; fi
    if test -n "$wireless"; then service_status=$service_status',"wireless":'$wireless; fi
    if test -n "$wireless"; then
        if factory_wireless; then wireless_factory=true; fi
        if file /tmp/open-connect/selected; then
            applied=$(cat /tmp/open-connect/selected)
            if snapshot_read "$applied" && test "$S_WIRELESS" = 1 &&
                file /tmp/open-connect/feature/wireless-applied &&
                test "$(cat /tmp/open-connect/feature/wireless-applied)" = 1; then wireless_current=1; fi
        fi
        service_status=$service_status',"wirelessCurrent":'$wireless_current',"wirelessFactory":'$wireless_factory
        test "$wireless" = "$wireless_current" || restart=true
    fi
    version=$(cat "$P/VERSION")
    case "$version" in ''|*[!a-zA-Z0-9.-]*) fail invalid_version;; esac
    # Keep the retired boolean false for an installed v0.2.0-dev.1 client during
    # USB handoff. No endpoint or UI offers Undo.
    printf '{"ok":true,"revision":"%s","installed":%s,"retained":%s,"undo":false,"conflict":%s,"restart":%s,"pending":%s,"touch":%s,"warning":%s,"notice":"%s","version":"%s","installedVersion":"%s","developer":%s,"uart":%s,"ssh":%s,"key":"%s","fingerprint":"%s","uartCurrent":%s,"sshCurrent":%s%s}\n' \
        "$rev" "$installed" "$retained" "$conflict" "$restart" "$pending" "$touch" "$warning" "$notice" "$version" \
        "$installed_version" "$developer" "$uart" "$owner_ssh" "$key" "$fingerprint" "$uart_current" "$ssh_current" "$service_status"
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
    old_package=-; touch=1; warning=1; uart=0; owner_ssh=0; key=-; pandora=1; base=0; wireless=0
    access_work=$(mktemp -d "$D/.access-XXXXXX") || fail access_plan_failed
    trap 'rm -rf "$access_work"' EXIT
    if test "$exists" = true && test "$R_PHASE" = active; then
        snapshot_read "$R_CURRENT" || fail invalid_snapshot
        old_package=$S_PACKAGE; touch=$S_TOUCH; warning=$S_WARNING; pandora=$S_PANDORA
        base=$S_BASE; wireless=$S_WIRELESS; before_pandora=$pandora; before_base=$base; before_wireless=$wireless
        if test "$S_CONFIG_FIELDS" = 5; then before_pandora=-; fi
        if test "$S_CONFIG_FIELDS" -lt 7; then before_base=-; fi
        if test "$S_CONFIG_FIELDS" -lt 8; then before_wireless=-; fi
        uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
        if test "$S_ACCESS" = true && test "$S_LOGIN_INODE" = -; then fail developer_reinstall_required; fi
        if test "$S_ACCESS" = false; then
            test "$(sha /usr/bin/runlogin)" = b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8 || fail unsupported_console
            absent "/usr/bin/.open-connect-runlogin-$(stat -c %i /usr/bin/runlogin)" || fail console_hold_conflict
        fi
        if test "$S_LOGIN_INODE" = -; then login_inode=$(stat -c %i /usr/bin/runlogin); else login_inode=$S_LOGIN_INODE; fi
        access_capture "$access_work" "$uart" "$owner_ssh" "$key" "$login_inode" || fail access_backup_failed
        selector_capture "$access_work" || fail selector_backup_failed
        before=$(state_capture "$old_package" "$touch" "$warning" "$access_work" "$before_pandora" "$before_base" "$before_wireless") || fail checkpoint_failed
        snapshot_read "$R_BASE" || fail originals_changed
        if test "$S_ACCESS" = false; then
            R_BASE=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - 0 0 "$S_NVRAM" "$S_META" "$D/snapshots/$R_BASE/dependencies" "$access_work") || fail access_backup_failed
        fi
    else
        test "$(sha "$AUTOSTART")" = "$(sha "$D/originals/autostart")" || fail unsupported_startup
        test "$(sha /usr/bin/runlogin)" = b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8 || fail unsupported_console
        absent "/usr/bin/.open-connect-runlogin-$(stat -c %i /usr/bin/runlogin)" || fail console_hold_conflict
        access_capture "$access_work" 0 0 - || fail access_backup_failed
        selector_capture "$access_work" || fail selector_backup_failed
        before=$(state_capture - 0 0 "$access_work") || fail checkpoint_failed
        R_BASE=$before
    fi
    package=$(package_save) || fail package_failed
    compose "$package" >/dev/null || fail composition_failed
    access_compose "$access_work" "$uart" "$owner_ssh" "$key" || fail access_plan_failed
    selector_compose "$access_work" "$package" || fail selector_plan_failed
    snapshot_read "$R_BASE" || fail originals_changed
    nvram=$S_NVRAM; mode=$S_META
    test "$touch" = 0 || nvram=disable
    deps=$(mktemp "$D/.dependencies-XXXXXX")
    dependencies_capture "$package" > "$deps" || fail checkpoint_dependencies_failed
    after=$(snapshot_create "$D/composed/$package/autostart" "$package" "$touch" "$warning" "$nvram" "$mode" "$deps" "$access_work" "$pandora" "$base" "$wireless") || fail plan_failed
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
    package=$S_PACKAGE; touch=$S_TOUCH; warning=$S_WARNING; pandora=$S_PANDORA; base=$S_BASE; wireless=$S_WIRELESS; mode=$S_META
    settings_schema=$S_CONFIG_FIELDS
    test "$argument" != pandora || test "$settings_schema" -ge 6 || fail services_update_required
    test "$argument" != base || test "$settings_schema" -ge 7 || fail services_update_required
    test "$argument" != wireless || test "$settings_schema" -ge 8 || fail wireless_update_required
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
        case "$argument:$expected:$desired" in
            touch:[01]:[01]) test "$touch" = "$expected" || fail stale_setting; touch=$desired;;
            warning:[01]:[01]) test "$warning" = "$expected" || fail stale_setting; warning=$desired;;
            pandora:[01]:[01]) test "$pandora" = "$expected" || fail stale_setting; pandora=$desired;;
            base:[01]:[01]) test "$base" = "$expected" || fail stale_setting; base=$desired;;
            wireless:[01]:[01]) test "$wireless" = "$expected" || fail stale_setting; wireless=$desired;;
            *) fail invalid_setting;;
        esac
    fi
    if test "$operation" = set && test "$expected" = "$desired"; then status; exit; fi
    snapshot_read "$R_BASE" || fail originals_changed
    nvram=$S_NVRAM; test "$touch" = 0 || nvram=disable
    service_choice=$pandora; base_choice=$base; wireless_choice=$wireless
    if test "$settings_schema" = 5; then service_choice=-; fi
    if test "$settings_schema" -lt 7; then base_choice=-; fi
    if test "$settings_schema" -lt 8; then wireless_choice=-; fi
    after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$touch" "$warning" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies" "$access_source" "$service_choice" "$base_choice" "$wireless_choice") || fail plan_failed
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
    after=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - 0 0 "$S_NVRAM" "$S_META" "$D/snapshots/$before/dependencies" "$resources") || fail plan_failed
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
