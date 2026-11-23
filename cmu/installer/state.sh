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
    local folder=$1 digest name extra expected= actual seen='|'
    directory "$folder" && file "$folder/files.sha256" || return 1
    set --
    while read -r digest name extra; do
        hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
        case "$name" in .|..|*[!a-zA-Z0-9.-]*) return 1;; esac
        case "$seen" in *"|$name|"*) return 1;; esac
        seen="$seen$name|"
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
# Active config is bounded OC2 named data. Dev.9 active8 and stock5 are read-only predecessor forms.
metadata() {
    S_META=$1
    S_MODE=${S_META%%:*}; local rest=${S_META#*:}
    S_UID=${rest%%:*}; S_GID=${rest#*:}
    test "$S_MODE:$S_UID:$S_GID" = "$S_META" || return 1
    case "$S_MODE" in [0-7]|[0-7][0-7]|[0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;; *) return 1;; esac
    case "$S_UID" in ''|*[!0-9]*) return 1;; esac
    case "$S_GID" in ''|*[!0-9]*) return 1;; esac
    test "${#S_UID}" -le 10 && test "${#S_GID}" -le 10 &&
        awk -v uid="$S_UID" -v gid="$S_GID" 'BEGIN{exit uid+0>4294967295 || gid+0>4294967295}'
}
snapshot_verify() {
    local dir=$D/snapshots/$1
    hex "$1" 64 && private_dir "$dir" && verify_manifest "$dir" &&
        test "$(sha "$dir/files.sha256")" = "$1"
}
snapshot_read() { snapshot_verify "$1" && snapshot_decode "$1"; }

# Read only the target package's preferences interpreter and catalog. Their
# expected bytes belong to the content-addressed manifest, not the USB client.
preferences_package() {
    local folder=$D/packages/$1 expected actual name
    hex "$1" 64 && private_dir "$folder" && file "$folder/files.sha256" &&
        test "$(sha "$folder/files.sha256")" = "$1" || return 1
    for name in preferences.awk services.tsv; do file "$folder/$name" || return 1; done
    expected=$(awk -v folder="$folder" '
        $2=="preferences.awk" {a++;p=$1;if(NF!=2)bad=1}
        $2=="services.tsv" {b++;s=$1;if(NF!=2)bad=1}
        END {
            if(bad||a!=1||b!=1||length(p)!=64||length(s)!=64||p~/[^a-f0-9]/||s~/[^a-f0-9]/)exit 1
            print p " *" folder "/preferences.awk"
            print s " *" folder "/services.tsv"
        }
    ' "$folder/files.sha256") || return 1
    actual=$(openssl dgst -sha256 -r "$folder/preferences.awk" "$folder/services.tsv") || return 1
    test "$actual" = "$expected" || return 1
    printf '%s\n' "$folder"
}

package_programs() {
    local folder=$D/packages/$1 name
    hex "$1" 64 && private_dir "$folder" && file "$folder/files.sha256" &&
        test "$(sha "$folder/files.sha256")" = "$1" && verify_manifest "$folder" || return 1
    shift
    for name in "$@"; do
        file "$folder/$name" &&
            awk -v name="$name" '$2==name{n++}END{exit n!=1}' "$folder/files.sha256" || return 1
    done
    printf '%s\n' "$folder"
}

preference_value() {
    printf '%s\n' "$1" | awk -F = -v key="$2" '$1==key{n++;v=$2}END{if(n!=1)exit 1;print v}'
}

preferences_change() (
    local prefs=$1 package=$2 key=$3 value=$4 schema=$5 folder=$P legacy=0
    if test "$schema" = OC2; then folder=$(preferences_package "$package") || return 1
    elif test "$schema" = dev9; then legacy=1
    else return 1; fi
    printf '%s\n' "$prefs" | awk -v operation=set -v catalog="$folder/services.tsv" -v catalog_bytes="$(wc -c < "$folder/services.tsv")" \
        -v input=/dev/stdin -v input_bytes="$((${#prefs}+1))" -v legacy="$legacy" \
        -v key="$key" -v value="$value" -f "$folder/preferences.awk"
)

config_decode() {
    local source=$1 header extra fields package folder decoded
    file "$source" && read -r header < "$source" || return 1
    if test "$header" = OC2; then
        package=$(awk -F = '$1=="package"{n++;p=$2}END{if(n!=1)exit 1;print p}' "$source") || return 1
        folder=$(preferences_package "$package") || return 1
        decoded=$(awk -v operation=decode -v catalog="$folder/services.tsv" -v catalog_bytes="$(wc -c < "$folder/services.tsv")" -v input="$source" \
            -v input_bytes="$(wc -c < "$source")" -f "$folder/preferences.awk") || return 1
        IFS='|' read -r S_PACKAGE S_TOUCH S_WARNING S_NVRAM S_META S_PANDORA S_BASE S_WIRELESS S_SERVICES extra <<VALUES
$decoded
VALUES
        test -z "$extra" && test "$S_PACKAGE" = "$package" || return 1
        S_SCHEMA=OC2; S_CONFIG_FIELDS=0
        S_PREFS=$(cat "$source") || return 1
    else
        # Only the actual predecessor is supported: five-field stock, or the
        # eight-field active dev.9 policy. No older active-schema migration.
        test "$(wc -l < "$source")" -eq 1 || return 1
        test "$(wc -c < "$source")" -eq "$((${#header}+1))" || return 1
        fields=$(awk -F '|' '{print NF}' "$source") || return 1
        case "$fields" in 5|8) ;; *) return 1;; esac
        IFS='|' read -r S_PACKAGE S_TOUCH S_WARNING S_NVRAM S_META S_PANDORA S_BASE S_WIRELESS extra < "$source" || return 1
        test -z "$extra" || return 1
        S_CONFIG_FIELDS=$fields
        if test "$fields" = 5; then
            test "$S_PACKAGE" = - || return 1
            S_SCHEMA=stock; S_PANDORA=1; S_BASE=0; S_WIRELESS=0; S_SERVICES=; S_PREFS=
        else
            hex "$S_PACKAGE" 64 || return 1
            S_SCHEMA=dev9; S_SERVICES=pandora=$S_PANDORA
            S_PREFS=$(printf 'OC2\nbase=%s\nmetadata=%s\nnvram=%s\npackage=%s\nservice.pandora=%s\ntouch=%s\nwarning=%s\nwireless=%s' \
                "$S_BASE" "$S_META" "$S_NVRAM" "$S_PACKAGE" "$S_PANDORA" "$S_TOUCH" "$S_WARNING" "$S_WIRELESS")
        fi
    fi
    bit "$S_TOUCH" && bit "$S_WARNING" && bit "$S_PANDORA" && bit "$S_BASE" &&
        bit "$S_WIRELESS" && touch_value "$S_NVRAM" && metadata "$S_META"
}

# Internal parser for snapshots already verified in the caller's held critical
# section. Ordinary callers use snapshot_read; no on-disk verification cache.
snapshot_decode() {
    local extra
    config_decode "$D/snapshots/$1/config" || return 1
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
    S_SELECTOR_RECORDED=false; S_SELECTOR_HASH=-; S_SELECTOR_META=-; S_SELECTOR_PACKAGE=-
    if ! absent "$D/snapshots/$1/selector"; then
        file "$D/snapshots/$1/selector" &&
            test "$(wc -l < "$D/snapshots/$1/selector")" -eq 1 &&
            awk '$2=="selector"{n++}END{exit n!=1}' "$D/snapshots/$1/files.sha256" || return 1
        S_SELECTOR_RECORDED=true
        if test "$(cat "$D/snapshots/$1/selector")" != -; then
            test "$(awk -F '|' '{print NF}' "$D/snapshots/$1/selector")" = 3 || return 1
            IFS='|' read -r S_SELECTOR_HASH S_SELECTOR_META S_SELECTOR_PACKAGE extra < "$D/snapshots/$1/selector" || return 1
            hex "$S_SELECTOR_HASH" 64 && hex "$S_SELECTOR_PACKAGE" 64 &&
                test "$S_SELECTOR_PACKAGE" = "$S_PACKAGE" &&
                test "$S_SELECTOR_META" = "700:$(id -u):$(id -g)" || return 1
        fi
    fi
}
snapshot_finish() (
    # Publish either a plain transaction snapshot or its verified boot plan.
    # The caller owns this private work directory and names every payload.
    set -eu
    local work=$1 id name digest seen='|'
    shift
    private_dir "$work" && test "$#" -gt 0 || fail invalid_snapshot_work
    case "$work" in "$D"/snapshots/.new-*) ;; *) fail invalid_snapshot_work;; esac
    absent "$work/files.sha256" || fail snapshot_manifest_exists
    for name in "$@"; do
        case "$name" in ''|.|..|files.sha256|*[!a-zA-Z0-9.-]*) fail invalid_snapshot_member;; esac
        case "$seen" in *"|$name|"*) fail invalid_snapshot_member;; esac
        seen="$seen$name|"
        file "$work/$name" || fail snapshot_member_missing
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

snapshot_create() (
    # autostart, target package, NVRAM, mode, dependencies, access, preferences.
    # Execute the verified target's writer: a newer USB is not its serializer.
    set -eu
    test "$#" = 7 || fail invalid_snapshot
    if test "$2" = -; then _snapshot_create "$@"; exit; fi
    local target fields touch warning pandora base wireless
    hex "$2" 64 || fail invalid_snapshot
    if ! absent "$D/packages/$2/preferences.awk"; then
        target=$(package_programs "$2" state.sh firmware.sh flush VERSION preferences.awk services.tsv sm-profile.awk) || fail invalid_snapshot_package
        sh -c 'set -eu; D=$1; P=$2; shift 2; . "$P/state.sh"; . "$P/firmware.sh"; _snapshot_create "$@"' \
            snapshot "$D" "$target" "$@"
    else
        target=$(package_programs "$2" state.sh firmware.sh flush VERSION) || fail invalid_snapshot_package
        # The one supported predecessor owns its eight-field active encoding.
        # Its stock before/after snapshots remain five fields, as recorded.
        file "$target/VERSION" && test "$(cat "$target/VERSION")" = 0.3.0-dev.9 || fail unsupported_snapshot_package
        fields=$(printf '%s\n' "$7" | awk -v operation=legacy -v catalog="$P/services.tsv" -v catalog_bytes="$(wc -c < "$P/services.tsv")" \
            -v input=/dev/stdin -v input_bytes="$((${#7}+1))" -f "$P/preferences.awk") || fail invalid_preferences
        IFS='|' read -r touch warning pandora base wireless <<VALUES
$fields
VALUES
        sh -c 'set -eu; D=$1; P=$2; shift 2; . "$P/state.sh"; snapshot_create "$@"' \
            snapshot "$D" "$target" "$1" "$2" "$touch" "$warning" "$3" "$4" "$5" "$6" "$pandora" "$base" "$wireless"
    fi
)

_snapshot_create() (
    # Target-owned current-format writer. All rendered policy is validated
    # before the caller can prepare a transaction or publish physical changes.
    set -eu
    test "$#" = 7 && file "$1" && { test "$2" = - || hex "$2" 64; } &&
        touch_value "$3" && metadata "$4" || fail invalid_snapshot
    local name resources=$6 prefs=$7 package=$2 nvram=$3 mode=$4
    work=$(mktemp -d "$D/snapshots/.new-XXXXXX") || fail snapshot_create_failed
    snapshot_work=$work
    trap 'if directory "$snapshot_work"; then rm -rf "$snapshot_work"; fi' EXIT
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
    fi
    snapshot_finish "$work" "$@"
)
