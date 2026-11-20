#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Access settings belong to the same immutable snapshots and transaction as the
# feature settings. Keys are immutable inputs, not a second settings record.

access_capture() {
    # Destination, requested UART/SSH state and imported key (or -).
    local dest=$1 uart=$2 ssh=$3 key=$4
    file /usr/bin/runlogin && file /etc/ssh/sshd_config || return 1
    cp /usr/bin/runlogin "$dest/runlogin" && cp /etc/ssh/sshd_config "$dest/sshd.conf" || return 1
    printf '%s|%s|%s|%s|%s\n' "$uart" "$ssh" "$key" \
        "$(stat -c '%a:%u:%g' /usr/bin/runlogin)" "$(stat -c '%a:%u:%g' /etc/ssh/sshd_config)" > "$dest/access"
}

access_key_verify() {
    hex "$1" 64 && private_dir "$D/keys" && file "$D/keys/$1.cmu" &&
        test "$(stat -c '%a:%u:%g' "$D/keys/$1.cmu")" = "600:$(id -u):$(id -g)" &&
        test "$(sha "$D/keys/$1.cmu")" = "$1"
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
    id=$(sha "$work"); hex "$id" 64 || fail key_hash_failed
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
    printf '%s|%s|%s|%s|%s\n' "$uart" "$ssh" "$key" "$S_LOGIN_META" "$S_SSH_META" > "$dest/access"
}

access_targets_match() {
    local dir=$D/snapshots/$1
    snapshot_read "$1" || return 1
    test "$S_ACCESS" = true || return 0
    file /usr/bin/runlogin && file /etc/ssh/sshd_config &&
        test "$(sha /usr/bin/runlogin)" = "$(sha "$dir/runlogin")" &&
        test "$(stat -c '%a:%u:%g' /usr/bin/runlogin)" = "$S_LOGIN_META" &&
        test "$(sha /etc/ssh/sshd_config)" = "$(sha "$dir/sshd.conf")" &&
        test "$(stat -c '%a:%u:%g' /etc/ssh/sshd_config)" = "$S_SSH_META" || return 1
    test "$S_KEY" = - || access_key_verify "$S_KEY"
}

access_pair_check() {
    local before=$D/snapshots/$1 after=$D/snapshots/$2 target name bh ah bm am actual
    if absent "$before/access" && absent "$after/access"; then return; fi
    snapshot_read "$1" && test "$S_ACCESS" = true || return 1
    snapshot_read "$2" && test "$S_ACCESS" = true || return 1
    test "$S_KEY" = - || access_key_verify "$S_KEY" || return 1
    for name in runlogin sshd.conf; do
        case "$name" in runlogin) target=/usr/bin/runlogin;; sshd.conf) target=/etc/ssh/sshd_config;; esac
        snapshot_read "$1"; bh=$(sha "$before/$name")
        if test "$name" = runlogin; then bm=$S_LOGIN_META; else bm=$S_SSH_META; fi
        snapshot_read "$2"; ah=$(sha "$after/$name")
        if test "$name" = runlogin; then am=$S_LOGIN_META; else am=$S_SSH_META; fi
        file "$target" || return 1
        actual=$(sha "$target"):$(stat -c '%a:%u:%g' "$target")
        case "$actual" in "$bh:$bm"|"$ah:$am") ;; *) return 1;; esac
    done
}

access_pair_apply() {
    local before=$D/snapshots/$1 after=$D/snapshots/$2 target name mode hash actual_mode before_hash before_mode
    absent "$after/access" && return 0
    for name in runlogin sshd.conf; do
        access_pair_check "$1" "$2" || return 1
        snapshot_read "$2" || return 1
        case "$name" in
            runlogin) target=/usr/bin/runlogin; mode=$S_LOGIN_META;;
            sshd.conf) target=/etc/ssh/sshd_config; mode=$S_SSH_META;;
        esac
        snapshot_read "$1" || return 1
        before_hash=$(sha "$before/$name")
        if test "$name" = runlogin; then before_mode=$S_LOGIN_META; else before_mode=$S_SSH_META; fi
        hash=$(sha "$target"); actual_mode=$(stat -c '%a:%u:%g' "$target")
        case "$hash:$actual_mode" in "$before_hash:$before_mode"|"$(sha "$after/$name"):$mode") ;; *) return 1;; esac
        root_publish "$target" "$after/$name" "$mode" "$hash" "$actual_mode" || return 1
    done
}
