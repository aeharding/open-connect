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
if test "$role:$operation:$argument" != settings:status:settings; then . "$P/service.sh"; fi
firmware_guard "$role:$operation:$argument"
private_dir /tmp/open-connect || fail runtime_unavailable
file /tmp/open-connect/lock || fail invalid_lock
if test "$operation:$argument" = dismiss:usb; then
  test "$role" = usb || fail invalid_request
  : > "$P/closed"
  printf '{"ok":true}\n'
  exit
fi
exec 9<>/tmp/open-connect/lock
if test "$operation:$argument" = status:settings; then flock -n -s 9 || fail busy
else flock -n -x 9 || fail busy; fi
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

completion_identity() {
  test "$role" = settings && test "$exists" = true || fail completion_unavailable
  settled || fail operation_pending
  test "$R_PHASE" = active && test "$selected_snapshot" = "$R_CURRENT" || fail completion_unavailable
  completion_boot=$(current_boot_id) && test "$completion_boot" = "$R_BOOT" || fail completion_unavailable
  test "$(snapshot_package "$R_CURRENT")" = "$R_BACKEND" || fail invalid_snapshot
  file "$P/files.sha256" && sha_is "$P/files.sha256" "$R_BACKEND" || fail session_replaced
  completion_version=$(package_version "$R_BACKEND") || fail invalid_version
  test "$(readlink -f "$runtime_pointer" 2>/dev/null || :)" = "$P" || fail session_replaced
}

selected_snapshot=$(selection_id /tmp/open-connect/selected) || selected_snapshot=
if test "$operation:$argument" = status:completion; then
  completion_identity
  completion_ready=false
  if test "$R_NOTICE" = installed; then
    completion_ready=true
    service_usb_observe >/dev/null 2>&1 || :
  fi
  printf '{"ok":true,"revision":"%s","package":"%s","boot":"%s","installedVersion":"%s","notice":"%s","completionReady":%s}\n' \
    "$R_CURRENT" "$R_BACKEND" "$completion_boot" "$completion_version" "$R_NOTICE" "$completion_ready"
  exit
fi
if test "$operation" = dismiss; then
  test "$role:$argument:$expected:$desired" = settings:-:-:- || fail invalid_request
  completion_identity
  test "$revision" = "$R_CURRENT" && test "$R_NOTICE" = installed || fail stale_state
  R_NOTICE=-; record_write
  : > "$P/closed"
  printf '{"ok":true}\n'
  exit
fi

# Open Connect pinned Settings 1
settings_package=
if test "$role" = settings && test "$exists" = true && test "$R_PHASE" != purge && test "$R_PHASE" != removed; then
  test -n "$selected_snapshot" || fail invalid_selected_snapshot
  settings_package=$(snapshot_package "$selected_snapshot") || fail invalid_selected_snapshot
  test "$settings_package" != - || fail invalid_selected_snapshot
fi

usb_metadata() {
  local installed=false retained=false pending=$empty_state restart=false rev=- notice=- version installed_version=- package
  if test "$exists" = true; then
    rev=$R_CURRENT; notice=$R_NOTICE
    if settled; then
      package=$(snapshot_package "$R_CURRENT") || fail invalid_snapshot
      if test "$R_PHASE" = active; then
        installed=true
        installed_version=$(package_version "$package") || fail invalid_version
        test "$selected_snapshot" = "$R_CURRENT" || restart=true
      else retained=true; fi
    else
      pending=true; restart=true; rev=$R_REV
    fi
  fi
  version=$(cat "$P/VERSION") || fail invalid_version
  case "$version" in ''|*[!a-zA-Z0-9.-]*) fail invalid_version;; esac
  test "$(readlink -f "$runtime_pointer" 2>/dev/null || :)" = "$P" || fail session_replaced
  test ! -f "$P/closed" || fail session_closed
  printf '{"ok":true,"revision":"%s","installed":%s,"retained":%s,"pending":%s,"restart":%s,"notice":"%s","version":"%s","installedVersion":"%s","completionReady":false}\n' \
    "$rev" "$installed" "$retained" "$pending" "$restart" "$notice" "$version" "$installed_version"
}

usb_retain() {
  if test "$role" = usb; then
    service_tick
    local current=-
    if test "$exists" = true; then current=$R_CURRENT; fi
    ln -s "OCUSB1|$((service_now+12000))|$current" "$P/admitted"
  fi
}

status_view() {
  local conflict=$1 installed=false retained=false touch=0 warning=0 notice=- rev=- restart=$removed_now pending=false
  local developer=false uart=0 owner_ssh=0 key=- fingerprint=- uart_current=0 ssh_current=0 wireless_current=0
  local installed_version=- installed_package=- pandora= base= wireless= autoshow= autoshow_current=0
  local saved_schema= saved_config= saved_catalog= selected_services= selected_wireless=0 rows=
  local selected= access_selected= view_id= touch_current= warning_current= base_current= selected_key=- restart_fixed=false
  selected=$selected_snapshot
  access_selected=$(selection_id /tmp/open-connect/access-selected) || access_selected=
  if test "$exists" = false && test -e /tmp/open-connect/selected; then restart=true; restart_fixed=true; fi
  if test "$empty_state" = true; then pending=true; fi
  if test "$exists" = true; then
    rev=$R_CURRENT; notice=$R_NOTICE
    if test "$R_PHASE" = purge; then
      rev=$R_REV; restart=true; restart_fixed=true; pending=true
    else
      view_id=$R_CURRENT
      if test -n "$settings_package"; then
        installed_package=$settings_package
        test "$R_CURRENT" = "$selected" || installed_package=$(snapshot_package "$R_CURRENT") || fail invalid_snapshot
        if test "$installed_package" != "$settings_package"; then view_id=$selected; restart=true; restart_fixed=true; fi
      fi
      snapshot_read "$view_id" || fail invalid_snapshot
      installed_package=$S_PACKAGE
      touch=$S_TOUCH; warning=$S_WARNING
      saved_schema=$S_SCHEMA
      if test "$S_SCHEMA" != stock; then
        pandora=$S_PANDORA; base=$S_BASE; wireless=$S_WIRELESS
      fi
      if test "$S_SCHEMA" = OC2; then
        case "$S_PREFS" in *'
carplay-autoshow='*) autoshow=$S_AUTOSHOW;; esac
        saved_config=$D/snapshots/$view_id/config
        saved_catalog=$S_CATALOG
      fi
      developer=$S_ACCESS; uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY
      if test "$key" != - && access_key_verify "$key"; then
        fingerprint=$(/usr/bin/ssh-keygen -l -f "$D/keys/$key.cmu" | awk '{print $2}')
        case "$fingerprint" in *[!a-f0-9:]|'') fingerprint=-;; esac
      fi
      if test "$R_PHASE" = active; then installed=true; fi
      if test "$R_PHASE" = removed; then retained=true; fi
      if test "$installed" = true && test "$conflict" = false; then
        installed_version=$(package_version "$installed_package") || installed_version=-
      fi
      if test "$R_PHASE" = active; then
        if test "$selected" != "$R_CURRENT"; then restart=true; fi
      elif test -e /tmp/open-connect/selected; then restart=true; restart_fixed=true; fi
      if ! settled; then restart=true; restart_fixed=true; pending=true; rev=$R_REV; fi
      if test "$access_selected" = "$view_id"; then uart_current=$uart; ssh_current=$owner_ssh; selected_key=$key; fi
      if test "$selected" = "$view_id"; then
        selected_services=$S_SERVICES; selected_wireless=$S_WIRELESS; autoshow_current=$S_AUTOSHOW
        touch_current=$touch; warning_current=$warning; base_current=$base
      elif test -n "$selected" && snapshot_read "$selected"; then
        selected_services=$S_SERVICES; selected_wireless=$S_WIRELESS; autoshow_current=$S_AUTOSHOW
        touch_current=$S_TOUCH; warning_current=$S_WARNING; base_current=$S_BASE
        if test "$access_selected" = "$selected"; then uart_current=$S_UART; ssh_current=$S_SSH; selected_key=$S_KEY; fi
      elif test "$R_PHASE" = active; then
        restart_fixed=true
      fi
      if test -n "$access_selected" && test "$access_selected" != "$view_id" && test "$access_selected" != "$selected"; then
        if snapshot_read "$access_selected"; then uart_current=$S_UART; ssh_current=$S_SSH; selected_key=$S_KEY; fi
      fi
      if test "$developer" = true && test "$key" != "$selected_key" && test "$owner_ssh" = 1; then restart_fixed=true; fi
    fi
  fi
  local version service_status= wireless_factory=false
  if test -n "$pandora"; then service_status=',"pandora":'$pandora; fi
  if test -n "$base"; then
    service_status=$service_status',"base":'$base
    if test -n "$base_current"; then service_status=$service_status',"baseCurrent":'$base_current; fi
  fi
  if test -n "$touch_current"; then service_status=$service_status',"touchCurrent":'$touch_current',"warningCurrent":'$warning_current; fi
  service_status=$service_status',"restartFixed":'$restart_fixed
  if test -n "$wireless"; then service_status=$service_status',"wireless":'$wireless; fi
  if test -n "$wireless"; then
    if factory_wireless; then wireless_factory=true
    else test "$?" = 1 || fail wireless_unavailable; fi
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
  printf '{"ok":true,"revision":"%s","installed":%s,"retained":%s,"undo":false,"conflict":%s,"restart":%s,"pending":%s,"touch":%s,"warning":%s,"notice":"%s","version":"%s","installedVersion":"%s","developer":%s,"uart":%s,"ssh":%s,"key":"%s","fingerprint":"%s","uartCurrent":%s,"sshCurrent":%s%s}\n' \
    "$rev" "$installed" "$retained" "$conflict" "$restart" "$pending" "$touch" "$warning" "$notice" "$version" \
    "$installed_version" "$developer" "$uart" "$owner_ssh" "$key" "$fingerprint" "$uart_current" "$ssh_current" "$service_status,\"completionReady\":false"
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
  if test "$role:$argument" = usb:settings; then usb_metadata
  elif test "$argument" = settings; then status_view false
  else status; fi
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
    test "$S_SCHEMA" = OC2 || test "$S_SCHEMA" = dev9 || fail unsupported_snapshot
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
  ;;
set|import)
  test "$exists" = true && test "$R_PHASE" = active || fail not_installed
  if test -n "$settings_package"; then
    test "$(snapshot_package "$R_CURRENT")" = "$settings_package" || fail restart_required
  fi
  FAST_READY=0; BOOT_SELECT=; SEAL_BOOT_PLAN=0
  case "$operation:$argument" in set:uart|set:ssh|import:*) ;; *)
    bs_rc=0; boot_select_verified || bs_rc=$?
    case "$bs_rc" in
      0) VERIFIED_PACKAGE=$R_BACKEND; S_CUR=; snapshot_decode "$R_CURRENT" || fail state_changed
         test "$S_SCHEMA:$S_PACKAGE" = "OC2:$R_BACKEND" || fail state_changed; FAST_READY=1;;
      2) BOOT_SELECT=;;
      *) fail state_changed;;
    esac;;
  esac
  if test "$FAST_READY" = 0; then targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed; VERIFIED_CURRENT=$R_CURRENT; VERIFIED_PACKAGE=$R_BACKEND; fi
  package=$S_PACKAGE; prefs=$S_PREFS; schema=$S_SCHEMA; mode=$S_META; test "$schema" = OC2 || test "$schema" = dev9 || fail unsupported_snapshot
  uart=$S_UART; owner_ssh=$S_SSH; key=$S_KEY; cur_nvram=$S_NVRAM; O_T2=0; test "$S_TOUCH" != 2 || O_T2=1
  O_W=$S_WARNING; O_B=$S_BASE; O_WL=$S_WIRELESS; O_S=$S_SERVICES; O_AS=$S_AUTOSHOW
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
  if test "$schema" = OC2; then
    test "$FAST_READY" = 1 || manifest_exact "$D/packages/$package" "" 0 "$package" || fail state_changed
    test "$package" = "$R_BACKEND" && ! absent "$D/packages/$package/boot-select" || SEAL_BOOT_PLAN=0
  else SEAL_BOOT_PLAN=0; fi
  if test "$operation:$expected" = "set:$desired"; then
    if test "$FAST_READY" = 1; then "$BOOT_SELECT" audit / "$R_CURRENT" || fail state_changed; S_VER="|$R_CURRENT|"; S_CUR=$R_CURRENT; fi
    status_view false; exit
  fi
  touch=$(preference_value "$prefs" touch) || fail invalid_preferences
  if test "$FAST_READY" = 1; then
    b=$D/snapshots/$R_BASE
    private_dir "$b" && file "$b/files.sha256" && sha_is "$b/files.sha256" "$R_BASE" &&
      snapshot_decode "$R_BASE" || fail originals_changed
    nvram=$S_NVRAM; test "$touch" != 1 || nvram=disable
    if fast_set_publish; then status_view false; exit; fi
    VERIFIED_CURRENT=; VERIFIED_PACKAGE=; BOOT_SELECT=; S_VER=; S_CUR=
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" &&
      manifest_exact "$D/packages/$package" "" 0 "$package" || fail state_changed
    VERIFIED_CURRENT=$R_CURRENT; VERIFIED_PACKAGE=$R_BACKEND
  fi
  test "$(preference_value "$prefs" base)" != 1 || native_log_inputs_verify || fail base_inputs_changed
  test "$touch" != 2 || touch_inputs_verify || fail touch_inputs_changed
  snapshot_read "$R_BASE" || fail originals_changed
  nvram=$S_NVRAM; test "$touch" != 1 || nvram=disable
  after=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$package" "$nvram" "$mode" "$D/snapshots/$R_CURRENT/dependencies" "$access_source" "$prefs") || fail plan_failed
  transaction_prepare set "$R_CURRENT" "$after"
  transaction_reconcile
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
