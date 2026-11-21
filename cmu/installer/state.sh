#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Shared data operations. Callers set D (persistent state) and P (verified code).
# Only D/record describes operation/startup state. Snapshots and packages are
# immutable inputs; temporary files never authorize writes or feature startup.

fail() { printf '%s\n' "$1" >&2; exit 1; }
sha() { local value; value=$(openssl dgst -sha256 < "$1") || return; printf '%s\n' "${value##* }"; }
hex() { test "${#1}" -eq "$2" && case "$1" in *[!a-f0-9]*) false;; *) true;; esac; }
uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }
absent() { test ! -e "$1" && test ! -L "$1"; }
file() { test -f "$1" && test ! -L "$1" && test "$(readlink -f "$1")" = "$1"; }
directory() { test -d "$1" && test ! -L "$1" && test "$(readlink -f "$1")" = "$1"; }
flush() { "$P/flush" "$1" "$2" || fail flush_failed; }
private_dir() {
    directory "$1" && test "$(stat -c '%a:%u:%g' "$1")" = "700:$(id -u):$(id -g)";
}
touch_value() { case "$1" in absent|enable|disable) true;; *) false;; esac; }
bit() { case "$1" in 0|1) true;; *) false;; esac; }
boot_id() {
    case "$1" in ????????-????-????-????-????????????) ;; *) return 1;; esac
    case "$1" in *[!a-f0-9-]*) return 1;; esac
}

verify_manifest() {
    local folder=$1 digest name extra expected= actual
    directory "$folder" && file "$folder/files.sha256" || return 1
    set --
    while read -r digest name extra; do
        hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
        case "$name" in .|..|*[!a-zA-Z0-9.-]*) return 1;; esac
        # The parent is already canonical, and names cannot contain a slash.
        test -f "$folder/$name" && test ! -L "$folder/$name" || return 1
        set -- "$@" "$folder/$name"
        expected="$expected$digest *$folder/$name
"
    done < "$folder/files.sha256"
    test "$#" -gt 0 || return 1
    # One process checks all bytes; repeated OpenSSL startup dominated early boot.
    actual=$(openssl dgst -sha256 -r "$@") || return 1
    test "$actual" = "${expected%?}"
}

record_read() {
    local format extra legacy_undo
    file "$D/record" && test "$(wc -l < "$D/record")" -eq 1 || return 1
    test "$(awk -F '|' '{print NF}' "$D/record")" = 13 || return 1
    IFS='|' read -r format R_PHASE R_REV R_BACKEND R_BASE R_CURRENT R_BEFORE R_AFTER legacy_undo R_BUDGET R_OFF R_BOOT R_NOTICE extra < "$D/record" || return 1
    test "$format" = OC1 && hex "$R_REV" 32 && hex "$R_BACKEND" 64 || return 1
    hex "$R_BASE" 64 && hex "$R_CURRENT" 64 || return 1
    # Read the retired checkpoint field for v0.2.0-dev.1 compatibility. New
    # records clear it; it never authorizes restoring an old installation.
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

record_write() {
    local next
    R_REV=$(uuid); hex "$R_REV" 32 || fail random_failed
    next=$(mktemp "$D/record.XXXXXX") || fail record_create_failed
    printf 'OC1|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n' \
        "$R_PHASE" "$R_REV" "$R_BACKEND" "$R_BASE" "$R_CURRENT" "$R_BEFORE" \
        "$R_AFTER" - "$R_BUDGET" "$R_OFF" "$R_BOOT" "$R_NOTICE" > "$next" || fail record_write_failed
    chmod 600 "$next" || fail record_mode_failed
    flush f "$next"
    mv -f "$next" "$D/record" || fail record_rename_failed
    flush d "$D"
    record_read || fail invalid_committed_record
}

# A snapshot contains an autostart file and data, not executable operation state.
# config = package | touch | warning | actual NVRAM | mode:uid:gid | Pandora | base | wireless
metadata() {
    S_META=$1
    S_MODE=${S_META%%:*}; local rest=${S_META#*:}
    S_UID=${rest%%:*}; S_GID=${rest#*:}
    test "$S_MODE:$S_UID:$S_GID" = "$S_META" || return 1
    case "$S_MODE" in [0-7]|[0-7][0-7]|[0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;; *) return 1;; esac
    case "$S_UID" in ''|*[!0-9]*) return 1;; esac
    case "$S_GID" in ''|*[!0-9]*) return 1;; esac
    test "${#S_UID}" -le 10 && test "${#S_GID}" -le 10
}
snapshot_verify() {
    local dir=$D/snapshots/$1
    hex "$1" 64 && private_dir "$dir" && verify_manifest "$dir" &&
        test "$(sha "$dir/files.sha256")" = "$1"
}
snapshot_read() {
    local extra fields
    snapshot_verify "$1" || return 1
    test "$(wc -l < "$D/snapshots/$1/config")" -eq 1 || return 1
    fields=$(awk -F '|' '{print NF}' "$D/snapshots/$1/config")
    case "$fields" in 5|6|7|8) ;; *) return 1;; esac
    S_CONFIG_FIELDS=$fields
    IFS='|' read -r S_PACKAGE S_TOUCH S_WARNING S_NVRAM S_META S_PANDORA S_BASE S_WIRELESS extra < "$D/snapshots/$1/config" || return 1
    # Older snapshots retained Mazda's original service policy.
    if test "$fields" = 5; then S_PANDORA=1; fi
    if test "$fields" -lt 7; then S_BASE=0; fi
    if test "$fields" -lt 8; then S_WIRELESS=0; fi
    test "$S_PACKAGE" = - || hex "$S_PACKAGE" 64 || return 1
    bit "$S_TOUCH" && bit "$S_WARNING" && bit "$S_PANDORA" && bit "$S_BASE" && bit "$S_WIRELESS" && touch_value "$S_NVRAM" || return 1
    metadata "$S_META" || return 1
    S_ACCESS=false; S_UART=0; S_SSH=0; S_KEY=-; S_LOGIN_META=-; S_SSH_META=-; S_LOGIN_INODE=-
    if ! absent "$D/snapshots/$1/access"; then
        local dir=$D/snapshots/$1
        file "$dir/runlogin" && file "$dir/sshd.conf" && file "$dir/access" || return 1
        test "$(wc -l < "$dir/access")" -eq 1 || return 1
        case "$(awk -F '|' '{print NF}' "$dir/access")" in 5|6) ;; *) return 1;; esac
        IFS='|' read -r S_UART S_SSH S_KEY S_LOGIN_META S_SSH_META S_LOGIN_INODE extra < "$dir/access" || return 1
        S_LOGIN_INODE=${S_LOGIN_INODE:--}
        case "$S_LOGIN_INODE" in -) ;; ''|*[!0-9]*) return 1;; esac
        bit "$S_UART" && bit "$S_SSH" && { test "$S_KEY" = - || hex "$S_KEY" 64; } || return 1
        test "$S_SSH" = 0 || hex "$S_KEY" 64 || return 1
        (metadata "$S_LOGIN_META" && metadata "$S_SSH_META") || return 1
        S_ACCESS=true
    fi
}
snapshot_create() (
    # Optional ninth/tenth/eleventh bits append Pandora/base/wireless. '-' preserves the older
    # installed selector's five/six/seven-field format until Install/update replaces it.
    # autostart, package, touch, warning, nvram, mode, dependencies, access, Pandora, base, wireless
    set -eu
    file "$1" && { test "$2" = - || hex "$2" 64; } && bit "$3" && bit "$4" &&
        { test "${9--}" = - || bit "${9--}"; } &&
        { test "${10--}" = - || { bit "${10--}" && test "${9--}" != -; }; } &&
        { test "${11--}" = - || { bit "${11--}" && test "${10--}" != -; }; } &&
        touch_value "$5" && metadata "$6" || fail invalid_snapshot
    local work id name digest
    work=$(mktemp -d "$D/snapshots/.new-XXXXXX") || fail snapshot_create_failed
    cp "$1" "$work/autostart" || fail snapshot_copy_failed
    if test "$#" -ge 7; then cp "$7" "$work/dependencies"; else : > "$work/dependencies"; fi || fail snapshot_copy_failed
    if test "${11--}" != -; then
        printf '%s|%s|%s|%s|%s|%s|%s|%s\n' "$2" "$3" "$4" "$5" "$6" "$9" "${10}" "${11}"
    elif test "${10--}" != -; then
        printf '%s|%s|%s|%s|%s|%s|%s\n' "$2" "$3" "$4" "$5" "$6" "$9" "${10}"
    elif test "${9--}" = -; then
        printf '%s|%s|%s|%s|%s\n' "$2" "$3" "$4" "$5" "$6"
    else
        printf '%s|%s|%s|%s|%s|%s\n' "$2" "$3" "$4" "$5" "$6" "$9"
    fi > "$work/config" || fail snapshot_config_failed
    chmod 600 "$work/autostart" "$work/config" "$work/dependencies" || fail snapshot_mode_failed
    set -- autostart config dependencies "${8:--}"
    if test "$4" != - && ! absent "$4/access"; then
        for name in access runlogin sshd.conf; do
            file "$4/$name" && cp "$4/$name" "$work/$name" && chmod 600 "$work/$name" || fail snapshot_copy_failed
        done
        set -- autostart config dependencies access runlogin sshd.conf
    else set -- autostart config dependencies; fi
    for name in "$@"; do
        digest=$(sha "$work/$name") && hex "$digest" 64 || fail snapshot_hash_failed
        printf '%s  %s\n' "$digest" "$name" || fail snapshot_manifest_failed
    done > "$work/files.sha256" || fail snapshot_manifest_failed
    chmod 600 "$work/files.sha256" || fail snapshot_mode_failed
    for name in "$@" files.sha256; do flush f "$work/$name"; done
    flush d "$work"
    id=$(sha "$work/files.sha256") && hex "$id" 64 || fail snapshot_hash_failed
    if absent "$D/snapshots/$id"; then
        mv "$work" "$D/snapshots/$id" || fail snapshot_publish_failed
        flush d "$D/snapshots"
    else
        snapshot_verify "$id" || fail snapshot_conflict
        for name in "$@" files.sha256; do rm "$work/$name" || fail snapshot_cleanup_failed; done
        rmdir "$work" || fail snapshot_cleanup_failed
    fi
    snapshot_read "$id" || fail snapshot_invalid
    printf '%s\n' "$id"
)
