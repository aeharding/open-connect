#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Access settings belong to the same immutable snapshots and transaction as the
# feature settings. Keys are immutable inputs, not a second settings record.

access_capture() {
  # Destination, requested UART/SSH state and imported key (or -).
  local dest=$1 uart=$2 ssh=$3 key=$4
  file /usr/bin/runlogin && file /etc/ssh/sshd_config || return 1
  cp /usr/bin/runlogin "$dest/runlogin" && cp /etc/ssh/sshd_config "$dest/sshd.conf" || return 1
  printf '%s|%s|%s|%s|%s|%s\n' "$uart" "$ssh" "$key" \
    "$(stat -c '%a:%u:%g' /usr/bin/runlogin)" "$(stat -c '%a:%u:%g' /etc/ssh/sshd_config)" \
    "${5:-$(stat -c %i /usr/bin/runlogin)}" > "$dest/access"
}

access_key_verify() {
  hex "$1" 64 && private_dir "$D/keys" && file "$D/keys/$1.cmu" &&
    test "$(stat -c '%a:%u:%g' "$D/keys/$1.cmu")" = "600:$(id -u):$(id -g)" &&
    sha_is "$D/keys/$1.cmu" "$1"
}

access_key_import() (
  set -eu
  # A fixed public-key filename on one mounted maintenance volume. Never
  # accept paths, authorized_keys options, private keys or shell text from UI.
  # Keep EXIT-trap inputs in this subshell's scope (BusyBox ash unwinds
  # function locals before an exit trap).
  source=; work=; volume=; id=; info=; bits=; kind=
  for volume in /tmp/mnt/sda1 /tmp/mnt/sdb1 /tmp/mnt/sdc1 /tmp/mnt/sdd1; do
    absent "$volume/open-connect.pub" && continue
    test -z "$source" || fail multiple_public_keys
    directory "$volume" && file "$volume/open-connect.pub" || fail invalid_public_key
    awk -v p="$volume" '$2==p && $3=="vfat"{n++} END{exit n!=1}' /proc/mounts || fail invalid_key_volume
    test "$(stat -c %s "$volume/open-connect.pub")" -le 8192 || fail invalid_public_key
    source=$volume/open-connect.pub
  done
  test -n "$source" || fail public_key_not_found
  private_dir "$D/keys" || fail invalid_key_directory
  work=$(mktemp "$D/keys/.new-XXXXXX") || fail key_create_failed
  trap 'rm -f "$work"' EXIT
  trap 'exit 1' HUP INT TERM
  awk '{sub(/\r$/, "")} NF {
    n++; if(n!=1 || NF<2 ||
      ($1!="ssh-rsa" && $1!="ecdsa-sha2-nistp256" && $1!="ecdsa-sha2-nistp384" && $1!="ecdsa-sha2-nistp521") ||
      $2 !~ /^[A-Za-z0-9+\/=]+$/) exit 1
    printf "%s %s\n",$1,$2
  } END{if(n!=1)exit 1}' "$source" > "$work" || fail unsupported_public_key
  info=$(/usr/bin/ssh-keygen -l -f "$work") || fail invalid_public_key
  bits=${info%% *}; kind=$(awk '{print $1}' "$work")
  case "$bits" in ''|*[!0-9]*) fail invalid_public_key;; esac
  if test "$kind" = ssh-rsa; then test "$bits" -ge 2048 || fail weak_public_key; fi
  chmod 600 "$work" || fail key_mode_failed
  id=$(sha "$work") && hex "$id" 64 || fail key_hash_failed
  flush f "$work"
  if absent "$D/keys/$id.cmu"; then
    mv "$work" "$D/keys/$id.cmu" || fail key_publish_failed
  else access_key_verify "$id" || fail key_changed; fi
  # A prior interrupted import may have renamed this same key without
  # flushing its directory. Make reuse durable before a record can refer to it.
  flush f "$D/keys/$id.cmu"
  flush d "$D/keys"
  printf '%s\n' "$id"
)

access_compose() {
  # Build target bytes from the pre-install access configuration, not from
  # our previous modifications. The imported key authorizes only UID-0 cmu.
  local dest=$1 uart=$2 ssh=$3 key=$4 base=$D/snapshots/$R_BASE
  snapshot_read "$R_BASE" && test "$S_ACCESS" = true || return 1
  bit "$uart" && bit "$ssh" || return 1
  test "$key" = - || access_key_verify "$key" || return 1
  cp "$base/runlogin" "$dest/runlogin" || return 1
  if test "$uart" = 1; then cp "$P/console.sh" "$dest/runlogin" || return 1; fi
  if test "$ssh" = 1; then
    access_key_verify "$key" || return 1
    test "$(awk -F: '$3==0{print $1}' /etc/passwd)" = cmu || return 1
    awk -v key="$key" '
      tolower($1)=="match" {bad=1;exit 1}
      tolower($1)=="authorizedkeysfile" {
        if(index($0,"#")){bad=1;exit 1}
        n++; print $0 " /data_persist/open-connect/keys/" key ".%u"; next
      }
      {print}
      END{if(bad || n!=1)exit 1}
    ' "$base/sshd.conf" > "$dest/sshd.conf" || return 1
  else cp "$base/sshd.conf" "$dest/sshd.conf" || return 1; fi
  /usr/sbin/sshd -t -f "$dest/sshd.conf" || return 1
  printf '%s|%s|%s|%s|%s|%s\n' "$uart" "$ssh" "$key" "$S_LOGIN_META" "$S_SSH_META" "$S_LOGIN_INODE" > "$dest/access"
}

access_hold_verify() ( snapshot_read "$R_BASE" && access_hold_verify_loaded; )

# These two helpers consume the already verified baseline snapshot fields.
access_hold_verify_loaded() (
  test "$S_LOGIN_INODE" != - || exit 1
  hold=/usr/bin/.open-connect-runlogin-$S_LOGIN_INODE
  file "$hold" && test "$(stat -c %i "$hold")" = "$S_LOGIN_INODE" &&
    test "$(stat -c %d "$hold")" = "$(stat -c %d /usr/bin/runlogin)" &&
    sha_same "$hold" "$D/snapshots/$R_BASE/runlogin" &&
    test "$(stat -c '%a:%u:%g' "$hold")" = "$S_LOGIN_META"
)

access_login_check() ( snapshot_read "$R_BASE" && access_login_check_loaded; )

access_login_check_loaded() (
  test "$S_LOGIN_INODE" != - || exit 0
  hold=/usr/bin/.open-connect-runlogin-$S_LOGIN_INODE
  if ! absent "$hold"; then access_hold_verify_loaded || exit 1; fi
  hash=$(sha /usr/bin/runlogin) && hex "$hash" 64 || exit 1
  base_hash=$(sha "$D/snapshots/$R_BASE/runlogin") && hex "$base_hash" 64 || exit 1
  if test "$hash" = "$base_hash"; then
    test "$(stat -c %i /usr/bin/runlogin)" = "$S_LOGIN_INODE"
  else access_hold_verify_loaded; fi
)

access_hold_cleanup() (
  set -eu
  snapshot_read "$R_BASE" || fail invalid_snapshot
  test "$S_LOGIN_INODE" != - || exit 0
  hold=/usr/bin/.open-connect-runlogin-$S_LOGIN_INODE
  test "$(stat -c %i /usr/bin/runlogin)" = "$S_LOGIN_INODE" || fail console_identity_changed
  if ! absent "$hold"; then
    access_hold_verify || fail console_hold_changed
    trap 'code=$?; trap - EXIT; remount ro || code=1; exit "$code"' EXIT
    remount rw || fail remount_failed
    # The restored pathname retains this same inode, including while the
    # original login process still has its script open.
    rm "$hold" || fail console_hold_cleanup_failed
  fi
  flush d /usr/bin
)

access_targets_match() {
  snapshot_read "$1" || return 1
  if test "$S_ACCESS" = true; then access_files_match_loaded "$1" && access_login_check; fi
}

access_files_match_loaded() {
  local dir=$D/snapshots/$1
  test "$S_ACCESS" = true || return 0
  file /usr/bin/runlogin && file /etc/ssh/sshd_config &&
    sha_same /usr/bin/runlogin "$dir/runlogin" &&
    test "$(stat -c '%a:%u:%g' /usr/bin/runlogin)" = "$S_LOGIN_META" &&
    sha_same /etc/ssh/sshd_config "$dir/sshd.conf" &&
    test "$(stat -c '%a:%u:%g' /etc/ssh/sshd_config)" = "$S_SSH_META" || return 1
  test "$S_KEY" = - || access_key_verify "$S_KEY"
}

access_pair_check() {
  local before=$D/snapshots/$1 after=$D/snapshots/$2 target name bh ah bm am actual
  A_PAIR_CHECKED=
  if absent "$before/access" && absent "$after/access"; then return; fi
  snapshot_read "$1" && test "$S_ACCESS" = true || return 1
  A_BEFORE_LOGIN=${S_LOGIN_META:-}; A_BEFORE_SSH=${S_SSH_META:-}
  snapshot_read "$2" && test "$S_ACCESS" = true || return 1
  A_AFTER_LOGIN=${S_LOGIN_META:-}; A_AFTER_SSH=${S_SSH_META:-}
  test "$S_KEY" = - || access_key_verify "$S_KEY" || return 1
  access_login_check || return 1
  for name in runlogin sshd.conf; do
    case "$name" in
      runlogin) target=/usr/bin/runlogin; bm=$A_BEFORE_LOGIN; am=$A_AFTER_LOGIN;;
      sshd.conf) target=/etc/ssh/sshd_config; bm=$A_BEFORE_SSH; am=$A_AFTER_SSH;;
    esac
    bh=$(sha "$before/$name") && hex "$bh" 64 || return 1
    ah=$(sha "$after/$name") && hex "$ah" 64 || return 1
    file "$target" || return 1
    actual=$(sha "$target") && hex "$actual" 64 || return 1
    actual=$actual:$(stat -c '%a:%u:%g' "$target")
    case "$actual" in "$bh:$bm"|"$ah:$am") ;; *) return 1;; esac
  done
  A_PAIR_CHECKED=$1:$2
}

access_login_hold() {
  local after_hash=$1 base_hash
  S_HOLD=; S_HOLD_MODE=
  snapshot_read "$R_BASE" || return 1
  test "$S_LOGIN_INODE" != - || return 0
  S_HOLD=/usr/bin/.open-connect-runlogin-$S_LOGIN_INODE
  base_hash=$(sha "$D/snapshots/$R_BASE/runlogin") && hex "$base_hash" 64 || return 1
  if test "$after_hash" = "$base_hash"; then
    if ! absent "$S_HOLD"; then S_HOLD_MODE=restore; else S_HOLD=; fi
  else S_HOLD_MODE=keep; fi
}

access_pair_apply() {
  local before=$D/snapshots/$1 after=$D/snapshots/$2 target name mode hash actual_mode before_hash before_mode after_hash hold hold_mode
  local b_login b_ssh a_login a_ssh
  absent "$after/access" && return 0
  if test "${A_PAIR_CHECKED:-}" = "$1:$2"; then
    b_login=$A_BEFORE_LOGIN; b_ssh=$A_BEFORE_SSH; a_login=$A_AFTER_LOGIN; a_ssh=$A_AFTER_SSH
    A_PAIR_CHECKED=
  else
    access_pair_check "$1" "$2" || return 1
    snapshot_read "$1" || return 1
    b_login=${S_LOGIN_META:-}; b_ssh=${S_SSH_META:-}
    snapshot_read "$2" || return 1
    a_login=${S_LOGIN_META:-}; a_ssh=${S_SSH_META:-}
    A_PAIR_CHECKED=
  fi
  for name in runlogin sshd.conf; do
    case "$name" in
      runlogin) target=/usr/bin/runlogin; before_mode=$b_login; mode=$a_login;;
      sshd.conf) target=/etc/ssh/sshd_config; before_mode=$b_ssh; mode=$a_ssh;;
    esac
    before_hash=$(sha "$before/$name") && hex "$before_hash" 64 || return 1
    after_hash=$(sha "$after/$name") && hex "$after_hash" 64 || return 1
    hash=$(sha "$target") && hex "$hash" 64 || return 1
    actual_mode=$(stat -c '%a:%u:%g' "$target") || return 1
    case "$hash:$actual_mode" in "$before_hash:$before_mode"|"$after_hash:$mode") ;; *) return 1;; esac
    if test -n "${PREPARED_REV:-}" && test "$PREPARED_REV" = "${R_REV:-}" && test "$before_hash:$before_mode" = "$after_hash:$mode" &&
      test "$hash:$actual_mode" = "$after_hash:$mode" &&
      absent "${target%/*}/.open-connect-$R_REV-${target##*/}" &&
      test "$(root_mode)" = ro,noatime; then
      continue
    fi
    hold=; hold_mode=
    if test "$name" = runlogin; then
      access_login_hold "$after_hash" || return 1
      hold=$S_HOLD; hold_mode=$S_HOLD_MODE
    fi
    root_publish "$target" "$after/$name" "$mode" "$hash" "$actual_mode" "$hold" "$hold_mode" || return 1
  done
}

fast_set_publish() {
  local w cfg oldP=$P skip='|' t2=0 rc=0
  w=$(mktemp -d "$D/snapshots/.new-XXXXXX") || fail plan_failed
  FAST_WORK=$w
  trap 'record_clean; rm -rf "${FAST_WORK:-}"' EXIT
  cfg=$(printf '%s\n' "$prefs" | awk -v operation=write -v catalog="$P/services.tsv" \
  -v catalog_bytes="$(wc -c < "$P/services.tsv")" -v package_id="$package" \
  -v nvram_value="$nvram" -v metadata_value="$mode" \
  -v input=/dev/stdin -v input_bytes="$((${#prefs}+1))" -f "$P/preferences.awk") || fail plan_failed
  printf '%s\n' "$cfg" > "$w/config" && config_decode "$w/config" || fail plan_failed
  test "$S_TOUCH" != 2 || t2=1
  test "$S_WARNING:$S_BASE:$S_SERVICES" != "$O_W:$O_B:$O_S" || skip="${skip}mmui|"
  test "$S_BASE:$S_SERVICES" != "$O_B:$O_S" || skip="${skip}plugins|"
  test "$t2:$S_WARNING:$S_BASE:$S_WIRELESS:$S_SERVICES" != "$O_T2:$O_W:$O_B:$O_WL:$O_S" || skip="${skip}sm|"
  test "$S_WARNING:$S_BASE:$S_SERVICES:$S_AUTOSHOW" != "$O_W:$O_B:$O_S:$O_AS" || skip="${skip}index|"
  if test "$skip" != '|mmui|plugins|sm|index|'; then
    P=$D/packages/$package; FAST_FROM=$R_CURRENT; FAST_SKIP=$skip
    boot_render_profiles "$w" "$w/config" || { P=$oldP; FAST_FROM=; FAST_SKIP=; fail state_changed; }
    P=$oldP; FAST_FROM=; FAST_SKIP=
  fi
  chmod 600 "$w"/* || fail plan_failed
  set -- seal-publish / "$R_CURRENT" "${w#/}"; test "$cur_nvram" = "$nvram" || set -- "$@" "$nvram"
  after=$("$BOOT_SELECT" "$@" 2>/dev/null) || rc=$?
  rm -rf "$w"; FAST_WORK=
  case "$rc" in 0) ;; 92) fail touch_inputs_changed;; 93) fail base_inputs_changed;; 95) return 2;; *) fail state_changed;; esac
  hex "$after" 64 && test "$(cat "$D/snapshots/$after/config")" = "$cfg" || fail plan_failed
  if test "$cur_nvram" != "$nvram"; then
  R_PHASE=set; R_BEFORE=$R_CURRENT; R_AFTER=$after
  record_stage prepare; record_publish || fail record_rename_failed
  nvram_change "$cur_nvram" "$nvram" || fail nvram_commit_failed
  "$BOOT_SELECT" audit / "$R_CURRENT" "$after" || fail final_verification_failed
  fi
  R_PHASE=active; R_CURRENT=$after; R_BEFORE=-; R_AFTER=-; R_BUDGET=3; R_OFF=-; R_BOOT=-; R_NOTICE=restart
  record_write; S_VER="|$after|"; S_CUR=
}
