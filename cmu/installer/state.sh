#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
request_owner=$(id -u) && request_owner=$request_owner:$(id -g) || exit 1
case "$request_owner" in :*|*:|*:*:*|*[!0-9:]*) exit 1;; esac

fail() { printf '%s\n' "$1" >&2; exit 1; }
sha() { "$P/flush" h "$1"; }
sha_many() { "$P/flush" H "$@"; }
hex() { test "${#1}" -eq "$2" && case "$1" in *[!a-f0-9]*) false;; *) true;; esac; }
sha_is() { local digest; digest=$(sha "$1") && hex "$digest" 64 && test "$digest" = "$2"; }
sha_same() { local digest; digest=$(sha "$1") && hex "$digest" 64 && sha_is "$2" "$digest"; }
uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }
absent() { test ! -e "$1" && test ! -L "$1"; }
file() { test -f "$1" && test ! -L "$1" && test "$(readlink -f "$1")" = "$1"; }
directory() { test -d "$1" && test ! -L "$1" && test "$(readlink -f "$1")" = "$1"; }
one_line() { file "$1" && IFS= read -r line < "$1" && test "$(wc -c < "$1")" -eq "$((${#line}+1))"; }
flush() { "$P/flush" "$1" "$2" || fail flush_failed; }
flush_files() { "$P/flush" F "$@" || fail flush_failed; }
private_dir() {
  directory "$1" && test "$(stat -c '%a:%u:%g' "$1")" = "700:$request_owner";
}
touch_value() { case "$1" in absent|enable|disable) true;; *) false;; esac; }
bit() { case "$1" in 0|1) true;; *) false;; esac; }
boot_id() {
  local value=$1 digit
  case "$1" in ????????-????-????-????-????????????) ;; *) return 1;; esac
  for digit in 1 2 3 4; do value=${value%%-*}${value#*-}; done
  hex "$value" 32
}

current_boot_id() {
  local marker=/tmp/open-connect/boot-id value
  test -L "$marker" && test "$(stat -c '%s:%u:%g' "$marker")" = "36:$request_owner" || return 1
  value=$(readlink "$marker") && boot_id "$value" || return 1
  printf '%s\n' "$value"
}

boot_identity() {
  local marker=/tmp/open-connect/boot-id kernel digest value digit
  if absent "$marker"; then
    kernel=$(cat /proc/sys/kernel/random/boot_id) && boot_id "$kernel" || return 1
    digest=$(printf 'OCBOOT1|%s|%s|%s|%s\n' "$kernel" "$R_REV" "$R_BOOT" "$R_OFF" | openssl dgst -sha256) || return 1
    digest=${digest##* }; hex "$digest" 64 || return 1
    value=$(printf '%s\n' "$digest" | sed 's/^\(........\)\(....\)\(....\)\(....\)\(............\).*/\1-\2-\3-\4-\5/') || return 1
    for digit in 0 1 2 3 4 5 6 7 8 9 a b c d e f; do
      if test "$value" != "$R_BOOT" && test "$value" != "$R_OFF"; then break; fi
      value=$digit${value#?}
    done
    ln -s "$value" "$marker" || return 1
  fi
  current_boot_id
}

verify_manifest() {
  local folder=$1 line digest name expected= actual seen='|' bytes=0
  verified_names=; verified_snapshot=
  directory "$folder" && file "$folder/files.sha256" || return 1
  set --
  while IFS= read -r line; do
    bytes=$((bytes+${#line}+1))
    digest=${line%% *}; name=${line#"$digest  "}
    hex "$digest" 64 && test "$line" = "$digest  $name" || return 1
    case "$name" in ''|.|..|*[!a-zA-Z0-9.-]*) return 1;; esac
    case "$seen" in *"|$name|"*) return 1;; esac
    seen="$seen$name|"
    test -f "$folder/$name" && test ! -L "$folder/$name" || return 1
    set -- "$@" "$folder/$name"
    expected="$expected$digest *$folder/$name
"
  done < "$folder/files.sha256"
  test "$#" -gt 0 && test "$(wc -c < "$folder/files.sha256")" -eq "$bytes" || return 1
  actual=$(sha_many "$@") || return 1
  test "$actual" = "${expected%?}" || return 1
  verified_names=$seen
}

record_read() {
  local line format extra legacy_undo
  one_line "$D/record" || return 1
  IFS='|' read -r format R_PHASE R_REV R_BACKEND R_BASE R_CURRENT R_BEFORE R_AFTER legacy_undo R_BUDGET R_OFF R_BOOT R_NOTICE extra < "$D/record" || return 1
  test "$line" = "OC1|$R_PHASE|$R_REV|$R_BACKEND|$R_BASE|$R_CURRENT|$R_BEFORE|$R_AFTER|$legacy_undo|$R_BUDGET|$R_OFF|$R_BOOT|$R_NOTICE" || return 1
  test "$format" = OC1 && hex "$R_REV" 32 && hex "$R_BACKEND" 64 || return 1
  hex "$R_BASE" 64 && hex "$R_CURRENT" 64 || return 1
  for extra in "$R_BEFORE" "$R_AFTER" "$legacy_undo"; do test "$extra" = - || hex "$extra" 64 || return 1; done
  case "$R_PHASE" in
    active|removed|purge) test "$R_BEFORE:$R_AFTER" = -:- || return 1;;
    install|set|uninstall|apply) hex "$R_BEFORE" 64 && hex "$R_AFTER" 64 || return 1;;
    *) return 1;;
  esac
  case "$R_BUDGET" in 0|1|2|3) ;; *) return 1;; esac
  test "$R_OFF" = - || boot_id "$R_OFF" || return 1
  test "$R_BOOT" = - || boot_id "$R_BOOT" || return 1
  case "$R_NOTICE" in -|installed|removed|undone|restart) ;; *) return 1;; esac
}

record_stage() {
  R_REV=$(uuid); hex "$R_REV" 32 || fail random_failed
  next=$(mktemp "$D/record.XXXXXX") || fail record_create_failed
  if test "${1:-}" = prepare; then prepared_candidate=$next; fi
  printf 'OC1|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n' \
    "$R_PHASE" "$R_REV" "$R_BACKEND" "$R_BASE" "$R_CURRENT" "$R_BEFORE" \
    "$R_AFTER" - "$R_BUDGET" "$R_OFF" "$R_BOOT" "$R_NOTICE" > "$next" || fail record_write_failed
  chmod 600 "$next" || fail record_mode_failed
  flush f "$next"
}

record_publish() {
  mv -f "$next" "$D/record" || return 1
  flush d "$D"
  record_read || fail invalid_committed_record
}

record_write() {
  local next
  record_stage
  record_publish || fail record_rename_failed
}

metadata() {
  S_META=$1
  S_MODE=${S_META%%:*}; local rest=${S_META#*:}
  S_UID=${rest%%:*}; S_GID=${rest#*:}
  test "$S_MODE:$S_UID:$S_GID" = "$S_META" || return 1
  case "$S_MODE" in [0-7]|[0-7][0-7]|[0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;; *) return 1;; esac
  case "$S_UID" in ''|*[!0-9]*) return 1;; esac
  case "$S_GID" in ''|*[!0-9]*) return 1;; esac
  test "${#S_UID}" -le 10 && test "${#S_GID}" -le 10 || return 1
  if test "${#S_UID}" -eq 10 || test "${#S_GID}" -eq 10; then
    awk -v uid="$S_UID" -v gid="$S_GID" 'BEGIN{exit uid+0>4294967295 || gid+0>4294967295}'
  fi
}
snapshot_verify() {
  local dir=$D/snapshots/$1
  if test "${S_CACHE:-0}" = 1; then
    case "${S_VER:-}" in *"|$1|"*) verified_snapshot=; return 0;; esac
  fi
  hex "$1" 64 && private_dir "$dir" && verify_manifest "$dir" &&
    sha_is "$dir/files.sha256" "$1" || return 1
  verified_snapshot=$1
  if test "${S_CACHE:-0}" = 1; then S_VER="${S_VER:-|}$1|"; fi
}
snapshot_read() {
  if test "${S_CACHE:-0}" = 1 && test "${S_CUR:-}" = "$1"; then
    case "${S_VER:-}" in *"|$1|"*) return 0;; esac
  fi
  S_CUR=
  snapshot_verify "$1" && snapshot_decode "$1" || return 1
  S_CUR=$1
}

snapshot_package() {
  local dir=$D/snapshots/$1 digest
  hex "$1" 64 && private_dir "$dir" && file "$dir/files.sha256" &&
    sha_is "$dir/files.sha256" "$1" && file "$dir/config" || return 1
  digest=$(awk '$2=="config"{n++;v=$1;if(NF!=2)bad=1}END{if(bad||n!=1)exit 1;print v}' "$dir/files.sha256") &&
    hex "$digest" 64 && sha_is "$dir/config" "$digest" || return 1
  awk '
        NR==1 {if($0=="OC2")modern=1;else {
            n=split($0,a,"|");if(n!=5||a[1]!="-"){bad=1;exit 1};p=a[1];count++
        }}
        NR>1&&!modern {bad=1;exit 1}
        modern&&/^package=/ {p=substr($0,9);count++}
        END {if(bad||count!=1||(p!="-"&&(length(p)!=64||p~/[^a-f0-9]/)))exit 1;print p}
    ' "$dir/config"
}

package_version() {
  local folder=$D/packages/$1 digest value
  if test "${VERIFIED_PACKAGE:-}" != "$1"; then
    hex "$1" 64 && private_dir "$folder" && file "$folder/files.sha256" &&
      sha_is "$folder/files.sha256" "$1" && file "$folder/VERSION" || return 1
    digest=$(awk '$2=="VERSION"{n++;v=$1;if(NF!=2)bad=1}END{if(bad||n!=1)exit 1;print v}' "$folder/files.sha256") &&
      hex "$digest" 64 && sha_is "$folder/VERSION" "$digest" || return 1
  else file "$folder/VERSION" || return 1; fi
  value=$(cat "$folder/VERSION") || return 1
  case "$value" in ''|*[!a-zA-Z0-9.-]*) return 1;; esac
  printf '%s\n' "$value"
}

preferences_package() {
  local folder=$D/packages/$1 digests p s name
  hex "$1" 64 && private_dir "$folder" || return 1
  if test "${VERIFIED_PACKAGE:-}" = "$1"; then
    test -f "$folder/preferences.awk" && test ! -L "$folder/preferences.awk" &&
      test -f "$folder/services.tsv" && test ! -L "$folder/services.tsv" || return 1
    printf '%s\n' "$folder"; return 0
  fi
  test -f "$folder/files.sha256" && test ! -L "$folder/files.sha256" &&
    sha_is "$folder/files.sha256" "$1" || return 1
  for name in preferences.awk services.tsv; do test -f "$folder/$name" && test ! -L "$folder/$name" || return 1; done
  digests=$(awk '
        $2=="preferences.awk"{a++;p=$1;if(NF!=2)bad=1}
        $2=="services.tsv"{b++;s=$1;if(NF!=2)bad=1}
        END{if(bad||a!=1||b!=1)exit 1;print p,s}
    ' "$folder/files.sha256") || return 1
  read -r p s <<DIGESTS
$digests
DIGESTS
  sha_is "$folder/preferences.awk" "$p" && sha_is "$folder/services.tsv" "$s" || return 1
  printf '%s\n' "$folder"
}

package_programs() {
  local folder=$D/packages/$1 name
  hex "$1" 64 && private_dir "$folder" && file "$folder/files.sha256" &&
    sha_is "$folder/files.sha256" "$1" && verify_manifest "$folder" || return 1
  shift
  test -x "$folder/flush" || return 1
  for name in flush "$@"; do
    file "$folder/$name" || return 1
    case "$verified_names" in *"|$name|"*) ;; *) return 1;; esac
  done
  printf '%s\n' "$folder"
}

preference_value() {
  printf '%s\n' "$1" | awk -F = -v key="$2" '$1==key{n++;v=$2}END{if(n!=1)exit 1;print v}'
}

preferences_change() (
  local prefs=$1 package=$2 key=$3 value=$4 schema=$5 folder
  test "$schema" = OC2 && folder=$(preferences_package "$package") || return 1
  printf '%s\n' "$prefs" | awk -v operation=set -v catalog="$folder/services.tsv" -v catalog_bytes="$(wc -c < "$folder/services.tsv")" \
    -v input=/dev/stdin -v input_bytes="$((${#prefs}+1))" \
    -v key="$key" -v value="$value" -f "$folder/preferences.awk"
)

config_decode() {
  local source=$1 header extra fields package folder decoded
  S_AUTOSHOW=0; S_CATALOG=
  file "$source" && read -r header < "$source" || return 1
  if test "$header" = OC2; then
    if test -n "${settings_package:-}"; then
      folder=$(preferences_package "$settings_package") || return 1
      package=
    else
      package=$(awk -F = '$1=="package"{n++;p=$2}END{if(n!=1)exit 1;print p}' "$source") || return 1
      folder=$(preferences_package "$package") || return 1
    fi
    S_CATALOG=$folder
    decoded=$(awk -v operation=decode -v catalog="$folder/services.tsv" -v catalog_bytes="$(wc -c < "$folder/services.tsv")" -v input="$source" \
      -v input_bytes="$(wc -c < "$source")" -f "$folder/preferences.awk") || return 1
    IFS='|' read -r S_PACKAGE S_TOUCH S_WARNING S_NVRAM S_META S_PANDORA S_BASE S_WIRELESS S_SERVICES extra <<VALUES
$decoded
VALUES
    test -z "$extra" && { test -z "$package" || test "$S_PACKAGE" = "$package"; } || return 1
    S_SCHEMA=OC2; S_CONFIG_FIELDS=0
    S_PREFS=$(cat "$source") || return 1
    case "$S_PREFS" in *'
carplay-autoshow='*)
      S_AUTOSHOW=${S_PREFS#*'
carplay-autoshow='}; S_AUTOSHOW=${S_AUTOSHOW%%'
'*};; esac
  else
    test "$(wc -l < "$source")" -eq 1 || return 1
    test "$(wc -c < "$source")" -eq "$((${#header}+1))" || return 1
    fields=$(awk -F '|' '{print NF}' "$source") || return 1
    test "$fields" = 5 || return 1
    IFS='|' read -r S_PACKAGE S_TOUCH S_WARNING S_NVRAM S_META extra < "$source" || return 1
    test -z "$extra" && test "$S_PACKAGE" = - || return 1
    S_CONFIG_FIELDS=5; S_SCHEMA=stock; S_PANDORA=1; S_BASE=0; S_WIRELESS=0; S_SERVICES=; S_PREFS=
  fi
  { bit "$S_TOUCH" || test "$S_SCHEMA:$S_TOUCH" = OC2:2; } && bit "$S_WARNING" && bit "$S_PANDORA" && bit "$S_BASE" &&
    bit "$S_WIRELESS" && touch_value "$S_NVRAM" && metadata "$S_META"
}

snapshot_decode() { snapshot_decode_dir "$D/snapshots/$1" "$1"; }
snapshot_decode_work() { S_CUR=; snapshot_decode_dir "$1" -; }
snapshot_decode_dir() {
  local extra line dir=$1 id=$2
  config_decode "$dir/config" || return 1
  S_ACCESS=false; S_UART=0; S_SSH=0; S_KEY=-; S_LOGIN_META=-; S_SSH_META=-; S_LOGIN_INODE=-
  if ! absent "$dir/access"; then
    test -f "$dir/runlogin" && test ! -L "$dir/runlogin" && test -f "$dir/sshd.conf" && test ! -L "$dir/sshd.conf" && one_line "$dir/access" || return 1
    IFS='|' read -r S_UART S_SSH S_KEY S_LOGIN_META S_SSH_META S_LOGIN_INODE extra < "$dir/access" || return 1
    test "$line" = "$S_UART|$S_SSH|$S_KEY|$S_LOGIN_META|$S_SSH_META" ||
      test "$line" = "$S_UART|$S_SSH|$S_KEY|$S_LOGIN_META|$S_SSH_META|$S_LOGIN_INODE" || return 1
    S_LOGIN_INODE=${S_LOGIN_INODE:--}
    case "$S_LOGIN_INODE" in -) ;; ''|*[!0-9]*) return 1;; esac
    bit "$S_UART" && bit "$S_SSH" && { test "$S_KEY" = - || hex "$S_KEY" 64; } || return 1
    test "$S_SSH" = 0 || hex "$S_KEY" 64 || return 1
    (metadata "$S_LOGIN_META" && metadata "$S_SSH_META") || return 1
    S_ACCESS=true
  fi
  S_SELECTOR_RECORDED=false; S_SELECTOR_HASH=-; S_SELECTOR_META=-; S_SELECTOR_PACKAGE=-
  if ! absent "$dir/selector"; then
    one_line "$dir/selector" || return 1
    if test "$id" != -; then
      if test "${verified_snapshot:-}" = "$id"; then
        case "${verified_names:-}" in *"|selector|"*) ;; *) return 1;; esac
      else
        awk '$2=="selector"{n++}END{exit n!=1}' "$dir/files.sha256" || return 1
      fi
    fi
    S_SELECTOR_RECORDED=true
    if test "$line" != -; then
      IFS='|' read -r S_SELECTOR_HASH S_SELECTOR_META S_SELECTOR_PACKAGE extra < "$dir/selector" || return 1
      test "$line" = "$S_SELECTOR_HASH|$S_SELECTOR_META|$S_SELECTOR_PACKAGE" &&
        hex "$S_SELECTOR_HASH" 64 && hex "$S_SELECTOR_PACKAGE" 64 &&
        test "$S_SELECTOR_PACKAGE" = "$S_PACKAGE" &&
        test "$S_SELECTOR_META" = "700:$request_owner" || return 1
    fi
  fi
}
sha_manifest() {
  local w=$1 h; shift
  h=$(cd "$w" && sha_many "$@") || return 1
  printf '%s\n' "$h" | awk -v n="$#" '{
    if(length($1)!=64||$1~/[^a-f0-9]/||substr($2,1,1)!="*"){b=1;exit 1}
    c++;print $1 "  " substr($2,2)
  }END{if(b||c!=n+0)exit 1}'
}
snapshot_finish() (
  set -eu
  local work=$1 id name seen='|'
  shift
  private_dir "$work" && test "$#" -gt 0 || fail invalid_snapshot_work
  case "$work" in "$D"/snapshots/.new-*) ;; *) fail invalid_snapshot_work;; esac
  absent "$work/files.sha256" || fail snapshot_manifest_exists
  for name in "$@"; do
    case "$name" in ''|.|..|files.sha256|*[!a-zA-Z0-9.-]*) fail invalid_snapshot_member;; esac
    case "$seen" in *"|$name|"*) fail invalid_snapshot_member;; esac
    seen="$seen$name|"
    test -f "$work/$name" && test ! -L "$work/$name" || fail snapshot_member_missing
  done
  sha_manifest "$work" "$@" > "$work/files.sha256" || fail snapshot_manifest_failed
  chmod 600 "$work/files.sha256" || fail snapshot_mode_failed
  set -- "$work/files.sha256" $(for name in "$@"; do printf '%s\n' "$work/$name"; done)
  flush_files "$@"
  flush d "$work"
  id=$(sha "$work/files.sha256") && hex "$id" 64 || fail snapshot_hash_failed
  if absent "$D/snapshots/$id"; then
    mv "$work" "$D/snapshots/$id" || fail snapshot_publish_failed
  else
    snapshot_verify "$id" || fail snapshot_conflict
    rm -f "$@" || fail snapshot_cleanup_failed
    rmdir "$work" || fail snapshot_cleanup_failed
  fi
  flush d "$D/snapshots"
  snapshot_read "$id" || fail snapshot_invalid
  printf '%s\n' "$id"
)

snapshot_create() (
  set -eu
  test "$#" = 7 || fail invalid_snapshot
  if test "$2" = -; then _snapshot_create "$@"; exit; fi
  local target
  hex "$2" 64 || fail invalid_snapshot
  ! absent "$D/packages/$2/preferences.awk" || fail unsupported_snapshot_package
  if test "${VERIFIED_PACKAGE:-}" = "$2" && private_dir "$D/packages/$2"; then
    target=$D/packages/$2
  else
    target=$(package_programs "$2" state.sh firmware.sh flush VERSION preferences.awk services.tsv sm-profile.awk) || fail invalid_snapshot_package
  fi
  sh -c 'set -eu; D=$1; P=$2; R_BASE=$3; R_BACKEND=$4; AUTOSTART=$5; SEAL_BOOT_PLAN=$6; VERIFIED_PACKAGE=$7; shift 7;
          . "$P/state.sh"; . "$P/firmware.sh";
          if test "$SEAL_BOOT_PLAN" = 1; then . "$P/access.sh"; fi;
          _snapshot_create "$@"' \
    snapshot "$D" "$target" "${R_BASE:-}" "${R_BACKEND:-}" "${AUTOSTART:-}" "${SEAL_BOOT_PLAN:-0}" "${VERIFIED_PACKAGE:-}" "$@"
)

_snapshot_create() (
  set -eu
  test "$#" = 7 && file "$1" && { test "$2" = - || hex "$2" 64; } &&
    touch_value "$3" && metadata "$4" || fail invalid_snapshot
  local name resources=$6 prefs=$7 package=$2 nvram=$3 mode=$4 hashes manifest
  work=$(mktemp -d "$D/snapshots/.new-XXXXXX") || fail snapshot_create_failed
  snapshot_work=$work
  trap 'if test -z "${initial_work:-}" && directory "$snapshot_work"; then rm -rf "$snapshot_work"; fi' EXIT
  cp "$1" "$work/autostart" || fail snapshot_copy_failed
  if test "$5" = -; then : > "$work/dependencies" || fail snapshot_copy_failed; else
    file "$5" && cp "$5" "$work/dependencies" || fail snapshot_copy_failed
  fi
  if test "$package" = -; then
    test -z "$prefs" || fail invalid_stock_preferences
    printf '%s|0|0|%s|%s\n' - "$nvram" "$mode" > "$work/config" || fail snapshot_config_failed
  elif test -z "$prefs"; then
    awk -v operation=write -v catalog="$P/services.tsv" -v catalog_bytes="$(wc -c < "$P/services.tsv")" -v package_id="$package" \
      -v nvram_value="$nvram" -v metadata_value="$mode" -f "$P/preferences.awk" > "$work/config" || fail snapshot_config_failed
  else
    printf '%s\n' "$prefs" | awk -v operation=write -v catalog="$P/services.tsv" -v catalog_bytes="$(wc -c < "$P/services.tsv")" \
      -v package_id="$package" -v nvram_value="$nvram" -v metadata_value="$mode" \
      -v input=/dev/stdin -v input_bytes="$((${#prefs}+1))" -f "$P/preferences.awk" > "$work/config" || fail snapshot_config_failed
  fi
  chmod 600 "$work/autostart" "$work/config" "$work/dependencies" || fail snapshot_mode_failed
  set -- autostart config dependencies
  if test "$resources" != - && ! absent "$resources/access"; then
    for name in access runlogin sshd.conf; do
      file "$resources/$name" && cp "$resources/$name" "$work/$name" && chmod 600 "$work/$name" || fail snapshot_copy_failed
    done
    set -- "$@" access runlogin sshd.conf
  fi
  if test "$resources" != - && ! absent "$resources/selector"; then
    file "$resources/selector" && cp "$resources/selector" "$work/selector" &&
      chmod 600 "$work/selector" || fail snapshot_copy_failed
    set -- "$@" selector
  fi
  if test "$package" != -; then
    boot_render_profiles "$work" "$work/config" || fail boot_profiles_failed
    for name in sm-normal.conf sm-wcp.conf index.html mmui.xml vui-plugins.list; do
      file "$work/$name" && chmod 600 "$work/$name" || fail snapshot_profile_failed
    done
    set -- "$@" sm-normal.conf sm-wcp.conf index.html mmui.xml vui-plugins.list
    if test "${SEAL_BOOT_PLAN:-0}" = 1 && test -n "${R_BASE:-}" && test "$package" = "${R_BACKEND:-}" &&
      test -x "$P/boot-select"; then
      manifest=$(sha_manifest "$work" "$@") || fail boot_plan_failed
      snapshot_decode_work "$work" || fail boot_plan_failed
      boot_plan_inputs "$work" - "$manifest" "$@" > "$work/inputs" || fail boot_inputs_failed
      "$P/boot-select" seal / "${work#/}" < "$work/inputs" > "$work/boot.plan" || fail boot_plan_failed
      rm "$work/inputs" && chmod 600 "$work/boot.plan" || fail boot_plan_failed
      set -- "$@" boot.plan
    fi
  fi
  snapshot_finish "$work" "$@"
)

gc_snap() {
  hex "${R_BACKEND:-}" 64 && test -n "${P:-}" && test -x "$P/api" && "$P/api" --gc "$R_BACKEND" 9 >/dev/null 2>&1 || :
}
