#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later

settled() { case "$R_PHASE" in active|removed) true;; *) false;; esac; }

dependencies_match() {
  local digest name extra target parent checked_parent= checked_root='|' expected= actual snapshot=$1 resolved first= deps deps_bytes fw_deps
  snapshot_verify "$1" || return 1
  deps=$D/snapshots/$snapshot/dependencies
  file "$deps" || return 1
  if test -s "$deps"; then read -r _ first _ < "$deps" || return 1; fi
  if command -v firmware_dependencies >/dev/null 2>&1 && case "$first" in */*) true;; *) false;; esac; then
    fw_deps=$(firmware_dependencies) || return 1
    deps_bytes=$(wc -c < "$deps") || return 1
    resolved=$(
      printf '%s\n' "$fw_deps" |
      awk -v D="$D" -v deps="$deps" -v expect="$deps_bytes" '
        NF==3 && $2!="autostart" { r[$2]=$3 }
        END {
          while((st=getline line < deps)>0) {
            bytes+=length(line)+1; n=split(line,f); cnt++
            if(n!=2||length(f[1])!=64||f[1]~/[^a-f0-9]/){bad=1;exit 1}
            sl=index(f[2],"/");if(!sl){bad=1;exit 1}
            sc=substr(f[2],1,sl-1);lf=substr(f[2],sl+1)
            if(lf==""||lf=="."||lf==".."||lf~/[^a-zA-Z0-9_.-]/){bad=1;exit 1}
            if(sc=="root"){if(!(lf in r)){bad=1;exit 1};t=r[lf]}
            else if(index(sc,"package-")==1){id=substr(sc,9);if(length(id)!=64||id~/[^a-f0-9]/){bad=1;exit 1};t=D "/packages/" id "/" lf}
            else if(index(sc,"composed-")==1){id=substr(sc,10);if(length(id)!=64||id~/[^a-f0-9]/){bad=1;exit 1};t=D "/composed/" id "/" lf}
            else{bad=1;exit 1}
            print f[1],sc,t
          }
          close(deps)
          if(bad||st<0||bytes!=expect+0||cnt<1) exit 1
        }
      '
    ) || return 1
    test -n "$resolved" || return 1
    set --
    while read -r digest name target; do
      case "$name" in package-*|composed-*)
        parent=${target%/*}
        if test "$parent" != "$checked_parent"; then private_dir "$parent" || return 1; checked_parent=$parent; fi
        test -f "$target" && test ! -L "$target" || return 1;;
      *) parent=${target%/*}
        case "$checked_root" in *"|$parent|"*) ;;
          *) directory "$parent" || return 1; checked_root="$checked_root$parent|";; esac
        test -f "$target" && test ! -L "$target" || return 1;; esac
      set -- "$@" "$target"
      expected="$expected$digest *$target
"
    done <<DEPS
$resolved
DEPS
  else
    set --
    while read -r digest name extra; do
      hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
      target=$(dependency_path "$name") || return 1
      case "$name" in package-*/*|composed-*/*)
        parent=${target%/*}
        if test "$parent" != "$checked_parent"; then private_dir "$parent" || return 1; checked_parent=$parent; fi
        test -f "$target" && test ! -L "$target" || return 1;;
      *) file "$target" || return 1;; esac
      set -- "$@" "$target"
      expected="$expected$digest *$target
"
    done < "$D/snapshots/$snapshot/dependencies"
  fi
  test "$#" -gt 0 || return 0
  actual=$(sha_many "$@") || return 1
  test "$actual" = "${expected%?}"
}

boot_dependencies_match() {
  local snapshot=$1 digest name extra scope leaf target parent checked= seen='|' mapping pin key path
  local members='|' member_count=1 package_count=0 manager=0 found expected= actual
  local composed='|' composed_count=0 composed_expected=1 root_count=0 root_expected=0
  while read -r digest name extra; do
    members="$members$name:$digest|"; member_count=$((member_count+1))
  done < "$P/files.sha256"
  members="${members}files.sha256:$R_BACKEND|"
  mapping=$(firmware_dependencies) || return 1
  while read -r pin key path; do
    if test "$key" != autostart; then root_expected=$((root_expected+1)); fi
  done <<PATHS
$mapping
PATHS
  parent=$D/composed/$R_BACKEND
  composed_members_verify "$parent" || return 1
  checked="|$parent|"
  while read -r digest name extra; do
    hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
    case "$name" in .|..|*[!a-zA-Z0-9_.-]*) return 1;; esac
    case "$composed" in *"|$name:"*) return 1;; esac
    composed="$composed$name:$digest|"; composed_expected=$((composed_expected+1))
  done < "$parent/files.sha256"
  set --
  while read -r digest name extra; do
    hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
    scope=${name%%/*}; leaf=${name#*/}
    test "$scope/$leaf" = "$name" || return 1
    case "$leaf" in ''|.|..|*[!a-zA-Z0-9_.-]*) return 1;; esac
    case "$seen" in *"|$name|"*) return 1;; esac
    seen="$seen$name|"
    case "$scope" in
     root)
      found=0; target=
      while read -r pin key path; do
        if test "$key" = "$leaf" && test "$key" != autostart; then
          target=$path; found=$((found+1))
        fi
      done <<PATHS
$mapping
PATHS
      test "$found" = 1 && file "$target" || return 1
      root_count=$((root_count+1))
      if test "$leaf" = manager.so; then native_dependency_guard "$digest" || return 1; manager=$((manager+1)); fi;;
     package-*|composed-*)
      if test "$scope" = "package-$R_BACKEND"; then parent=$P
      elif test "$scope" = "composed-$R_BACKEND"; then parent=$D/composed/$R_BACKEND
      else return 1; fi
      case "$checked" in *"|$parent|"*) ;;
        *) private_dir "$parent" || return 1; checked="$checked|$parent|";; esac
      target=$parent/$leaf
      test -f "$target" && test ! -L "$target" || return 1
      if test "$scope" = "package-$R_BACKEND"; then
        case "$members" in *"|$leaf:$digest|"*) ;; *) return 1;; esac
        package_count=$((package_count+1)); continue
      fi
      if test "$leaf" != files.sha256; then
        case "$composed" in *"|$leaf:$digest|"*) ;; *) return 1;; esac
      fi
      composed_count=$((composed_count+1));;
     *) return 1;;
    esac
    set -- "$@" "$target"
    expected="$expected$digest *$target
"
  done < "$D/snapshots/$snapshot/dependencies"
  test "$package_count" = "$member_count" && test "$manager" = 1 &&
    test "$root_count" = "$root_expected" && test "$composed_count" = "$composed_expected" &&
    test "$#" -gt 0 || return 1
  actual=$(sha_many "$@") || return 1
  test "$actual" = "${expected%?}"
}

dependencies_pair_match() {
  dependencies_match "$1" || return 1
  if cmp -s "$D/snapshots/$1/dependencies" "$D/snapshots/$2/dependencies"; then
    snapshot_verify "$2"
  else
    dependencies_match "$2"
  fi
}

targets_match() {
  snapshot_read "$1" && targets_match_loaded "$1" || return 1
  if test "$S_ACCESS" = true; then access_login_check; fi
}

targets_match_loaded() {
  file "$AUTOSTART" &&
    sha_same "$AUTOSTART" "$D/snapshots/$1/autostart" &&
    test "$(stat -c '%a:%u:%g' "$AUTOSTART")" = "$S_META" &&
    test "$(nvram_read)" = "$S_NVRAM" || return 1
  if test "$S_ACCESS" = true; then access_files_match_loaded "$1" || return 1; fi
  if test "${S_SELECTOR_RECORDED:-false}" = true; then selector_matches_loaded || return 1; fi
}

state_capture() (
  set -eu
  test "$#" = 3 || fail invalid_checkpoint
  local deps result
  deps=$(mktemp "$D/.dependencies-XXXXXX") || fail checkpoint_create_failed
  dependencies_capture "$1" > "$deps" || fail checkpoint_dependencies_failed
  result=$(snapshot_create "$AUTOSTART" "$1" "$(nvram_read)" "$(stat -c '%a:%u:%g' "$AUTOSTART")" "$deps" "$2" "$3") || fail checkpoint_failed
  rm "$deps"
  printf '%s\n' "$result"
)

uninstall_owned() (
  local current_mode current_touch current_nvram snapshot=$1
  snapshot_read "$snapshot" || return 1
  hex "$S_PACKAGE" 64 && file "$D/composed/$S_PACKAGE/autostart" &&
    sha_same "$D/snapshots/$snapshot/autostart" "$D/composed/$S_PACKAGE/autostart" || return 1
  current_mode=$S_META; current_touch=$S_TOUCH; current_nvram=$S_NVRAM
  snapshot_read "$R_BASE" || return 1
  test "$current_mode" = "$S_META" || return 1
  test "$current_nvram" = "$S_NVRAM" || test "$current_touch:$current_nvram" = 1:disable
)

prepared_candidate=
record_clean() {
  if test -n "$prepared_candidate"; then rm -f "$prepared_candidate" || :; fi
  if test -n "${initial_work:-}" && private_dir "$initial_work" &&
    test "$(stat -c '%d:%i' "$initial_work")" = "$initial_identity" &&
    ( D=$initial_work; cleanup_mount_guard ); then rm -rf "$initial_work" || :; fi
}

initial_begin() {
  local path
  if test "$exists" = false; then
    absent "$D" || fail invalid_record
    initial_destination=$D
    D=$(mktemp -d "${D%/*}/.open-connect-initial-XXXXXX") || fail state_create_failed
    initial_work=$D
    initial_identity=$(stat -c '%d:%i' "$D") || fail state_create_failed
  fi
  for path in snapshots packages composed keys; do
    if absent "$D/$path"; then mkdir -m 700 "$D/$path" || fail state_create_failed; fi
    private_dir "$D/$path" || fail invalid_state_directory
  done
  flush d "$D"
}

initial_publish() {
  if test "$exists" = false; then
    R_PHASE=removed; R_CURRENT=$before; R_BEFORE=-; R_AFTER=-
    R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-
    record_write
    absent "$initial_destination" || fail state_create_failed
    mv "$D" "$initial_destination" || fail state_publish_failed
    D=$initial_destination; initial_work=
    access_work=$D/${access_work##*/}; exists=true
  fi
  if test "$R_PHASE" = removed; then flush d "${D%/*}"; fi
}

retained_match() {
  originals_verify || return 1
  test "$R_BASE" = "$R_CURRENT" ||
    { targets_match "$R_BASE" && dependencies_match "$R_BASE"; }
}

transaction_prepare() {
  local next
  settled || fail operation_pending
  if test "$1" = set; then
    cmp -s "$D/snapshots/$2/dependencies" "$D/snapshots/$3/dependencies" || fail invalid_plan
  fi
  if test "${VERIFIED_CURRENT:-}" = "$2" && cmp -s "$D/snapshots/$2/dependencies" "$D/snapshots/$3/dependencies"; then
    snapshot_read "$3" || fail invalid_plan
  else
    snapshot_read "$2" && snapshot_read "$3" || fail invalid_plan
    targets_match "$2" && dependencies_pair_match "$2" "$3" || fail state_changed
  fi
  R_PHASE=$1; R_BEFORE=$2; R_AFTER=$3
  record_stage prepare
  if command -v transaction_admit >/dev/null 2>&1; then transaction_admit; fi
  if ! record_publish; then
    if file "$next" && command -v usb_fence_restore >/dev/null 2>&1; then usb_fence_restore; fi
    fail record_rename_failed
  fi
  PREPARED_REV=$R_REV
}

transaction_reconcile() {
  settled && return
  local before_hash after_hash before_mode after_mode before_nv after_nv actual_hash actual_mode actual_nv phase
  phase=$R_PHASE
  if test "$phase" = uninstall; then
    test "$R_BEFORE" = "$R_CURRENT" || fail state_changed
    uninstall_owned "$R_BEFORE" || fail state_changed
  fi
  snapshot_read "$R_BEFORE" || fail invalid_before
  before_hash=$(sha "$D/snapshots/$R_BEFORE/autostart") && hex "$before_hash" 64 || fail invalid_before
  before_mode=$S_META; before_nv=$S_NVRAM
  snapshot_read "$R_AFTER" || fail invalid_after
  after_hash=$(sha "$D/snapshots/$R_AFTER/autostart") && hex "$after_hash" 64 || fail invalid_after
  after_mode=$S_META; after_nv=$S_NVRAM
  if test "${PREPARED_REV:-}" != "$R_REV"; then
    dependencies_pair_match "$R_BEFORE" "$R_AFTER" || fail dependencies_changed
    flush d "$D"
  fi
  file "$AUTOSTART" || fail startup_changed
  actual_hash=$(sha "$AUTOSTART") && hex "$actual_hash" 64 || fail startup_changed
  actual_mode=$(stat -c '%a:%u:%g' "$AUTOSTART"); actual_nv=$(nvram_read) || fail nvram_unreadable
  case "$actual_hash:$actual_mode" in "$before_hash:$before_mode"|"$after_hash:$after_mode") ;; *) fail startup_changed;; esac
  case "$actual_nv" in "$before_nv"|"$after_nv") ;; *) fail nvram_changed;; esac
  if test ! -e "$D/snapshots/$R_BEFORE/access" && test ! -e "$D/snapshots/$R_AFTER/access"; then :
  else access_pair_check "$R_BEFORE" "$R_AFTER" || fail access_changed; fi
  selector_pair=false
  if ! absent "$D/snapshots/$R_BEFORE/selector" || ! absent "$D/snapshots/$R_AFTER/selector"; then
    selector_pair_check "$R_BEFORE" "$R_AFTER" || fail selector_changed
    selector_pair=true
  fi
  if command -v transaction_admit >/dev/null 2>&1; then transaction_admit; fi
  if test "$phase" = set || test "$phase" = install; then
    snapshot_read "$R_AFTER" || fail invalid_after
    if test "$S_TOUCH" = 2 && ! touch_inputs_verify; then
      PREPARED_REV=; VERIFIED_CURRENT=; VERIFIED_PACKAGE=; A_PAIR_CHECKED=; SEAL_BOOT_PLAN=0; S_VER=; S_CUR=
      startup_staging_retire "$R_AFTER" || fail startup_stage_changed
      snapshot_read "$R_BEFORE" || fail invalid_before
      if test "$phase" = set && test "$S_TOUCH" != 2; then
        local rollback=$R_BEFORE
        R_BEFORE=$R_AFTER; R_AFTER=$rollback
      else
        snapshot_read "$R_AFTER" || fail invalid_after
        local source=$D/snapshots/$R_AFTER prefs
        prefs=$(preferences_change "$S_PREFS" "$S_PACKAGE" touch 0 "$S_SCHEMA") || fail invalid_preferences
        R_AFTER=$(snapshot_create "$source/autostart" "$S_PACKAGE" "$S_NVRAM" "$S_META" "$source/dependencies" "$source" "$prefs") || fail plan_failed
      fi
      record_write
      transaction_reconcile; return
    fi
  fi
  if test "$phase" != uninstall; then
    if test "$selector_pair" = true; then
      if test -n "${PREPARED_REV:-}" && test "$PREPARED_REV" = "${R_REV:-}" && test "$phase" = set &&
        cmp -s "$D/snapshots/$R_BEFORE/selector" "$D/snapshots/$R_AFTER/selector" &&
        absent "/usr/bin/.open-connect-$R_REV-open-connect-boot-select" &&
        test "$(root_mode)" = ro,noatime; then :
      else selector_apply "$R_BEFORE" "$R_AFTER" || fail selector_apply_failed; fi
    fi
    startup_publish "$D/snapshots/$R_AFTER/autostart" "$after_mode" "$actual_hash" "$actual_mode"
  fi
  if test -e "$D/snapshots/$R_AFTER/access"; then
    access_pair_apply "$R_BEFORE" "$R_AFTER" || fail access_apply_failed
  fi
  if test "$before_nv" != "$after_nv"; then
    nvram_change "$actual_nv" "$after_nv" || fail nvram_commit_failed
  fi
  if test "$phase" = uninstall; then
    startup_publish "$D/snapshots/$R_AFTER/autostart" "$after_mode" "$actual_hash" "$actual_mode"
    if test -e "$D/snapshots/$R_AFTER/access"; then access_hold_cleanup || fail access_cleanup_failed; fi
    if test "$selector_pair" = true; then selector_apply "$R_BEFORE" "$R_AFTER" || fail selector_remove_failed; fi
  fi
  S_VER=; S_CUR=
  if test "$selector_pair" = true; then
    selector_pair_check "$R_AFTER" "$R_AFTER" || fail selector_verification_failed
  fi
  targets_match "$R_AFTER" && dependencies_match "$R_AFTER" || fail final_verification_failed
  if test "$phase" != uninstall && test "$S_PACKAGE" != - &&
    ! absent "$D/packages/$S_PACKAGE/boot-select"; then
    R_AFTER=$(boot_snapshot_seal "$R_AFTER") || fail boot_snapshot_failed
    snapshot_read "$R_AFTER" || fail invalid_boot_snapshot
  fi
  R_CURRENT=$R_AFTER
  case "$phase" in
    uninstall) R_PHASE=removed; R_NOTICE=removed; R_BUDGET=0;;
    install) R_PHASE=active; R_NOTICE=installed; R_BUDGET=3;;
    set) R_PHASE=active; R_NOTICE=restart; R_BUDGET=3;;
    apply) R_PHASE=active;;
  esac
  R_BEFORE=-; R_AFTER=-
  if test "$phase" != apply; then R_OFF=-; R_BOOT=-; fi
  record_write
}

uninstall_cleanup() {
  private_dir "$D" || fail invalid_state_directory
  case "$P" in "$D"|"$D"/*) fail cleanup_requires_ram;; esac
  test "$(root_mode)" = ro,noatime || fail root_mount_changed
  cleanup_mount_guard || fail cleanup_mount_present
  if absent "$D/record"; then
    rmdir "$D" || fail invalid_cleanup_state
    flush d "${D%/*}"
    return
  fi
  record_read || fail invalid_record
  case "$R_PHASE" in
    removed)
      targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
      startup_staging_guard || fail startup_stage_changed
      if command -v transaction_admit >/dev/null 2>&1; then transaction_admit; fi
      R_PHASE=purge
      record_write;;
    purge) ;; # Durable restoration proof survives deletion of its snapshots.
    *) fail not_removed;;
  esac
  local path
  for path in "$D"/* "$D"/.[!.]* "$D"/..?*; do
    absent "$path" && continue
    test "${path##*/}" != record || continue
    rm -rf "$path" || fail cleanup_failed
  done
  flush d "$D"
  rm "$D/record" || fail cleanup_failed
  flush d "$D"
  rmdir "$D" || fail cleanup_failed
  flush d "${D%/*}"
}
