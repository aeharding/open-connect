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
    local folder=$1 digest name extra count=0
    directory "$folder" && file "$folder/files.sha256" || return 1
    while read -r digest name extra; do
        hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
        case "$name" in .|..|*[!a-zA-Z0-9.-]*) return 1;; esac
        file "$folder/$name" && test "$(sha "$folder/$name")" = "$digest" || return 1
        count=$((count+1))
    done < "$folder/files.sha256"
    test "$count" -gt 0
}

record_read() {
    local format extra
    file "$D/record" && test "$(wc -l < "$D/record")" -eq 1 || return 1
    test "$(awk -F '|' '{print NF}' "$D/record")" = 13 || return 1
    IFS='|' read -r format R_PHASE R_REV R_BACKEND R_BASE R_CURRENT R_BEFORE R_AFTER R_UNDO R_BUDGET R_OFF R_BOOT R_NOTICE extra < "$D/record" || return 1
    test "$format" = OC1 && hex "$R_REV" 32 && hex "$R_BACKEND" 64 || return 1
    hex "$R_BASE" 64 && hex "$R_CURRENT" 64 || return 1
    for extra in "$R_BEFORE" "$R_AFTER" "$R_UNDO"; do test "$extra" = - || hex "$extra" 64 || return 1; done
    case "$R_PHASE" in
        active|removed) test "$R_BEFORE:$R_AFTER" = -:- || return 1;;
        install|set|uninstall|undo|apply) hex "$R_BEFORE" 64 && hex "$R_AFTER" 64 || return 1;;
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
        "$R_AFTER" "$R_UNDO" "$R_BUDGET" "$R_OFF" "$R_BOOT" "$R_NOTICE" > "$next" || fail record_write_failed
    chmod 600 "$next" || fail record_mode_failed
    flush f "$next"
    mv -f "$next" "$D/record" || fail record_rename_failed
    flush d "$D"
    record_read || fail invalid_committed_record
}

# A snapshot contains an autostart file and data, not executable operation state.
# config = package | touch preference | warning preference | actual NVRAM | mode:uid:gid
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
    local extra
    snapshot_verify "$1" || return 1
    test "$(wc -l < "$D/snapshots/$1/config")" -eq 1 &&
        test "$(awk -F '|' '{print NF}' "$D/snapshots/$1/config")" = 5 || return 1
    IFS='|' read -r S_PACKAGE S_TOUCH S_WARNING S_NVRAM S_META extra < "$D/snapshots/$1/config" || return 1
    test "$S_PACKAGE" = - || hex "$S_PACKAGE" 64 || return 1
    bit "$S_TOUCH" && bit "$S_WARNING" && touch_value "$S_NVRAM" || return 1
    metadata "$S_META"
}
snapshot_create() (
    # source autostart, package, touch, warning, nvram, original mode
    set -eu
    file "$1" && { test "$2" = - || hex "$2" 64; } && bit "$3" && bit "$4" && touch_value "$5" && metadata "$6" || fail invalid_snapshot
    local work id name digest
    work=$(mktemp -d "$D/snapshots/.new-XXXXXX") || fail snapshot_create_failed
    cp "$1" "$work/autostart" || fail snapshot_copy_failed
    if test "$#" -eq 7; then cp "$7" "$work/dependencies"; else : > "$work/dependencies"; fi || fail snapshot_copy_failed
    printf '%s|%s|%s|%s|%s\n' "$2" "$3" "$4" "$5" "$6" > "$work/config" || fail snapshot_config_failed
    chmod 600 "$work/autostart" "$work/config" "$work/dependencies" || fail snapshot_mode_failed
    for name in autostart config dependencies; do
        digest=$(sha "$work/$name") && hex "$digest" 64 || fail snapshot_hash_failed
        printf '%s  %s\n' "$digest" "$name" || fail snapshot_manifest_failed
    done > "$work/files.sha256" || fail snapshot_manifest_failed
    chmod 600 "$work/files.sha256" || fail snapshot_mode_failed
    for name in autostart config dependencies files.sha256; do flush f "$work/$name"; done
    flush d "$work"
    id=$(sha "$work/files.sha256") && hex "$id" 64 || fail snapshot_hash_failed
    if absent "$D/snapshots/$id"; then
        mv "$work" "$D/snapshots/$id" || fail snapshot_publish_failed
        flush d "$D/snapshots"
    else
        snapshot_verify "$id" || fail snapshot_conflict
        rm "$work/autostart" "$work/config" "$work/dependencies" "$work/files.sha256" && rmdir "$work" || fail snapshot_cleanup_failed
    fi
    snapshot_read "$id" || fail snapshot_invalid
    printf '%s\n' "$id"
)
