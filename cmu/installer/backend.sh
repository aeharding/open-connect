#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
set -eu
umask 077
export LC_ALL=C
P=$(dirname "$(readlink -f "$0")")
D=/tmp/mnt/data_persist/open-connect
AUTOSTART=/usr/bin/autostart
case "${1:-}:${3:-}:${4:-}:$#" in
  api:status:settings:6|api:status:completion:6|api:dismiss:usb:6|api:dismiss:-:6)
    exec "$P/api" --handle "$P" "$2" "$3" "$4" "$5" "$6";;
esac
. "$P/state.sh"
. "$P/firmware.sh"
. "$P/access.sh"
. "$P/transaction.sh"
. "$P/service.sh"
trap record_clean EXIT

fail() {
  printf '{"ok":false,"error":"%s"}\n' "$1"; exit 1
}
test "${1:-}" = api && test "$#" -eq 6 || fail invalid_request
revision=$2; operation=$3; argument=$4; expected=$5; desired=$6

runtime_pointer=/tmp/open-connect/runtime
role=settings
if test "$(readlink -f "$runtime_pointer" 2>/dev/null || :)" != "$P"; then
  runtime_pointer=/tmp/open-connect/usb-runtime
  test "$(readlink -f "$runtime_pointer" 2>/dev/null || :)" = "$P" || fail session_replaced
  role=usb
fi
firmware_guard "$role:$operation:$argument"
private_dir /tmp/open-connect || fail runtime_unavailable
file /tmp/open-connect/lock || fail invalid_lock
exec 9<>/tmp/open-connect/lock
flock -n -x 9 || fail busy
test "$(readlink -f "$runtime_pointer" 2>/dev/null || :)" = "$P" || fail session_replaced
S_CACHE=1; S_VER=; S_CUR=
if test "$role" = usb && test "$operation" != status; then
  if test -f "$P/closed"; then
    test "$operation" = restart && service_usb_retained "$P" || fail session_closed
  fi
  case "$operation" in install|uninstall|recover|restart) ;; *) fail invalid_request;; esac
fi

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
if test "$exists:$empty_state" = false:false && ! absent "$D"; then fail invalid_record; fi

selection_id() {
  local value
  file "$1" && test "$(wc -c < "$1")" -eq 65 && test "$(wc -l < "$1")" -eq 1 &&
    IFS= read -r value < "$1" && hex "$value" 64 || return 1
  printf '%s\n' "$value"
}

status_identity() {
  local marker path value
  if absent "$D/record"; then printf 'record=absent\n'
  else
    file "$D/record" && value=$(sha "$D/record") && hex "$value" 64 || return 1
    printf 'record=%s\n' "$value"
  fi
  for marker in selected access-selected boot-id; do
    path=/tmp/open-connect/$marker
    if absent "$path"; then printf '%s=absent\n' "$marker"
    elif test -L "$path"; then
      value=$(readlink "$path") || return 1
      printf '%s=link:%s\n' "$marker" "$value"
    elif file "$path"; then
      value=$(sha "$path") && hex "$value" 64 || return 1
      printf '%s=file:%s\n' "$marker" "$value"
    else return 1; fi
  done
}

selected_snapshot=$(selection_id /tmp/open-connect/selected) || selected_snapshot=

# Open Connect pinned Settings 1
settings_package=
if test "$role" = settings && test "$exists" = true && test "$R_PHASE" != purge && test "$R_PHASE" != removed; then
  test -n "$selected_snapshot" || fail invalid_selected_snapshot
  settings_package=$(snapshot_package "$selected_snapshot") || fail invalid_selected_snapshot
  test "$settings_package" != - || fail invalid_selected_snapshot
fi

usb_retain() {
  if test "$role" = usb; then
    service_tick
    local current=-
    if test "$exists" = true; then current=$R_CURRENT; fi
    ln -s "OCUSB1|$((service_now+12000))|$current" "$P/admitted"
  fi
}

status_view() {
  "$P/api" --status-view "$P" "$1" "$removed_now" "$empty_state" "${settings_package:--}"
}

access_snapshot() {
  snapshot_create "$D/snapshots/$1/autostart" - "$S_NVRAM" "$S_META" "$D/snapshots/$1/dependencies" "$access_work" ""
}

status() {
  local conflict=false audit_identity= audit_after=
  if test "$exists" = true && test "$R_PHASE" != purge; then
    if test "$operation" = status; then
      audit_identity=$(status_identity) || fail state_changed
      S_CACHE=0; S_VER=; S_CUR=
      flock -u 9 || fail invalid_lock
    fi
    if ! (targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT"); then conflict=true; fi
    if test "$operation" = status; then
      flock -n -x 9 || fail busy
      test "$(readlink -f "$runtime_pointer" 2>/dev/null || :)" = "$P" || fail session_replaced
      S_CACHE=1; S_VER=; S_CUR=
      audit_after=$(status_identity) || fail state_changed
      test "$audit_after" = "$audit_identity" || fail busy
    fi
  fi
  if test "$operation" != status; then usb_retain; fi
  status_view "$conflict"
}

transaction_admit() {
  if test "$role:${transaction_admitted:-0}" = usb:0; then
    usb_helpers=true; . "$P/usb-service.sh"
    usb_fence; transaction_admitted=1
  fi
}

finish_removal() {
  uninstall_cleanup
  exists=false; empty_state=false; removed_now=true
}

if test "$operation" = status; then
  status
  exit
fi
if test "$role" = usb; then rm -f "$P/admitted"; fi
if test "$exists" = true; then
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
  verify_manifest "$P" || fail incomplete_maintenance_bundle
  test "$(root_mode)" = ro,noatime || fail root_mount_changed
  if test "$exists" = true; then
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    if test "$R_PHASE" = removed; then
      retained_match || fail originals_changed
    fi
  fi
  stock_dependencies || fail unsupported_original
  initial_begin
  originals_save
  old_package=-; prefs=; uart=0; owner_ssh=0; key=-
  access_work=$(mktemp -d "$D/.access-XXXXXX") || fail access_plan_failed
  trap 'record_clean; test -n "${initial_work:-}" || rm -rf "$access_work"' EXIT
  if test "$exists" = true && test "$R_PHASE" = active; then
    snapshot_read "$R_CURRENT" || fail invalid_snapshot
    test "$S_SCHEMA" = OC2 || fail unsupported_snapshot
    old_package=$S_PACKAGE; prefs=$S_PREFS
    uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
    if test "$S_ACCESS" = true && test "$S_LOGIN_INODE" = -; then fail developer_reinstall_required; fi
    if test "$S_ACCESS" = false; then
      sha_is /usr/bin/runlogin b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8 || fail unsupported_console
      absent "/usr/bin/.open-connect-runlogin-$(stat -c %i /usr/bin/runlogin)" || fail console_hold_conflict
    fi
    if test "$S_LOGIN_INODE" = -; then login_inode=$(stat -c %i /usr/bin/runlogin); else login_inode=$S_LOGIN_INODE; fi
    access_capture "$access_work" "$uart" "$owner_ssh" "$key" "$login_inode" || fail access_backup_failed
    selector_capture "$access_work" || fail selector_backup_failed
    before=$(state_capture "$old_package" "$access_work" "$prefs") || fail checkpoint_failed
  else
    sha_same "$AUTOSTART" "$D/originals/autostart" || fail unsupported_startup
    sha_is /usr/bin/runlogin b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8 || fail unsupported_console
    absent "/usr/bin/.open-connect-runlogin-$(stat -c %i /usr/bin/runlogin)" || fail console_hold_conflict
    access_capture "$access_work" 0 0 - || fail access_backup_failed
    selector_capture "$access_work" || fail selector_backup_failed
    if test "$exists" = true; then
      before=$R_CURRENT
      snapshot_read "$before" || fail invalid_snapshot
      if test "$S_ACCESS" = false; then before=$(access_snapshot "$before") || fail checkpoint_failed; fi
    else
      before=$(state_capture - "$access_work" "") || fail checkpoint_failed
      R_BASE=$before
    fi
  fi
  if test "$exists" = true; then
    snapshot_read "$R_BASE" || fail originals_changed
    if test "$S_ACCESS" = false; then
      R_BASE=$(access_snapshot "$R_BASE") || fail access_backup_failed
    fi
  fi
  if test -n "$prefs" && test "$(preference_value "$prefs" base)" = 1; then native_log_inputs_verify || fail base_inputs_changed; fi
  package=$(package_save) || fail package_failed
  R_BACKEND=$package
  initial_publish
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
  transaction_prepare install "$before" "$after"
  transaction_reconcile
  gc_snap
  ;;
set|import)
  test "$exists" = true && test "$R_PHASE" = active || fail not_installed
  if test -n "$settings_package"; then
    test "$(snapshot_package "$R_CURRENT")" = "$settings_package" || fail restart_required
  fi
  SEAL_BOOT_PLAN=0
  targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
  VERIFIED_CURRENT=$R_CURRENT; VERIFIED_PACKAGE=$R_BACKEND
  package=$S_PACKAGE; prefs=$S_PREFS; schema=$S_SCHEMA; mode=$S_META; test "$schema" = OC2 || fail unsupported_snapshot
  uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
  access_source=$D/snapshots/$R_CURRENT
  if test "$operation" = import || test "$argument" = uart || test "$argument" = ssh; then
    test "$S_ACCESS" = true || fail developer_update_required
    test "$S_LOGIN_INODE" != - || fail developer_reinstall_required
    access_work=$(mktemp -d "$D/.access-XXXXXX") || fail access_plan_failed
    trap 'record_clean; rm -rf "$access_work"' EXIT
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
    case "$argument:$expected:$desired" in touch:[012]:[012]|*:[01]:[01]) ;; *) fail invalid_setting;; esac
    case "$argument" in
      touch|warning|base|wireless|carplay-autoshow) preference_key=$argument;;
      *) preference_key=service.$argument;;
    esac
    actual=$(preference_value "$prefs" "$preference_key") || fail invalid_setting
    test "$actual" = "$expected" || fail stale_setting
    prefs=$(preferences_change "$prefs" "$package" "$preference_key" "$desired" "$schema") || fail invalid_setting
    SEAL_BOOT_PLAN=1
  fi
  manifest_exact "$D/packages/$package" "" 0 "$package" || fail state_changed
  test "$package" = "$R_BACKEND" && ! absent "$D/packages/$package/boot-select" || SEAL_BOOT_PLAN=0
  if test "$operation:$expected" = "set:$desired"; then
    status_view false; exit
  fi
  touch=$(preference_value "$prefs" touch) || fail invalid_preferences
  test "$(preference_value "$prefs" base)" != 1 || native_log_inputs_verify || fail base_inputs_changed
  test "$touch" != 2 || touch_inputs_verify || fail touch_inputs_changed
  snapshot_read "$R_BASE" || fail originals_changed
  nvram=$S_NVRAM; test "$touch" != 1 || nvram=disable
  after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies" "$access_source" "$prefs") || fail plan_failed
  transaction_prepare set "$R_CURRENT" "$after"
  transaction_reconcile
  gc_snap
  status_view false; exit
  ;;
uninstall)
  test "$exists" = true || fail not_installed
  if test "$R_PHASE" = removed; then finish_removal; status; exit; fi
  test "$R_PHASE" = active || fail not_installed
  targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
  uninstall_owned "$R_CURRENT" || fail state_changed
  before=$R_CURRENT
  selector_recorded=$S_SELECTOR_RECORDED
  snapshot_read "$R_BASE" || fail originals_changed
  resources=$D/snapshots/$R_BASE
  if test "$selector_recorded" = true && test "$S_SELECTOR_RECORDED" = false; then
    resources=$(mktemp -d "$D/.access-XXXXXX") || fail selector_plan_failed
    trap 'record_clean; rm -rf "$resources"' EXIT
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
restart)
  if test "$exists" = true; then
    settled || fail operation_pending
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
  else
    absent "$D" || fail operation_pending
  fi
  test "$(root_mode)" = ro,noatime || fail root_mount_changed
  usb_retain
  ( sleep 2; /bin/busybox timeout -t 10 /sbin/reboot ) </dev/null >/dev/null 2>&1 &
  printf '{"ok":true,"restarting":true}\n'
  exit
  ;;
*) fail invalid_request;;
esac
status
