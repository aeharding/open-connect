#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Per-device touchscreen preference on firmware 55.00.750B North America.
set -eu
export LC_ALL=C
store=/sys/class/nvram/nv-config
key=lvds_speed_restriction

valid() {
    case "$1" in absent|enable|disable) return 0 ;; *) return 1 ;; esac
}

read_value() {
    if [ -f "$store/keys/$key" ]; then
        stored=$(cat "$store/keys/$key") || return 1
        case "$stored" in enable|disable) printf '%s\n' "$stored" ;; *) return 1 ;; esac
    elif [ -r "$store/keys" ] && [ -x "$store/keys" ] && [ ! -e "$store/keys/$key" ]; then
        printf '%s\n' absent
    else
        return 1
    fi
}

case "${1:-}:$#" in
    read:1|install:1|uninstall:1) ;;
    change:3) valid "$2" && valid "$3" || exit 64 ;;
    *) exit 64 ;;
esac
awk '
    $0 == "JCI_SW_VER=\"MAZ_CMU-150_55.00.750\"" {v++}
    $0 == "JCI_SW_VER_PATCH=\"B\"" {p++}
    $0 == "JCI_SW_FLAVOR=\"cmu150_NA\"" {f++}
    END {exit !(v==1 && p==1 && f==1)}
' /jci/version.ini || exit 65
[ "$(md5sum < /jci/lvds/lvds_service)" = '6bb6b50fb459f3a152b6528efbf5a95c  -' ] || exit 65

action=$1
if [ "$action" != read ]; then
    # Serialize Open Connect operations. Other services may also own NVRAM.
    lock=/tmp/oc-lvds-setting.lock
    mkdir -m 700 "$lock" || exit 75
    tmp=
    trap 'if [ -n "$tmp" ]; then rm -f "$tmp"; fi; rmdir "$lock"' EXIT
    trap 'exit 1' HUP INT TERM
fi
value=$(read_value) || exit 74
valid "$value" || exit 65
if [ "$1" = read ]; then printf '%s\n' "$value"; exit 0; fi
if [ "$action" = install ] || [ "$action" = uninstall ]; then
    volume=/tmp/mnt/data_persist
    receipt="$volume/.open-connect-touch-original-v1"
    flush="$(dirname "$0")/flush-arm"
    awk -v path="$volume" '$1=="/dev/mmcblk0p2" && $2==path && $3=="relfs" && $4 ~ /^rw(,|$)/ {n++}
        END {exit n!=1}' /proc/mounts || exit 65
    [ "$(stat -c '%u:%g:%a' "$volume")" = '0:0:755' ] || exit 65
    [ ! -L "$receipt" ] || exit 73
    if [ ! -e "$receipt" ]; then
        if [ "$action" = uninstall ]; then
            "$flush" d "$volume"
            printf 'unmanaged\n'
            exit 0
        fi
        umask 077
        tmp=$(mktemp "$volume/.oc-touch-XXXXXX") || exit 74
        printf '%s\n' "$value" > "$tmp"
        "$flush" f "$tmp"
        mv "$tmp" "$receipt"
        tmp=
    fi
    [ -f "$receipt" ] && [ "$(stat -c '%u:%g:%a:%h' "$receipt")" = '0:0:600:1' ] || exit 73
    [ "$(wc -c < "$receipt")" -le 8 ] || exit 73
    original=$(cat "$receipt")
    valid "$original" || exit 73
    printf '%s\n' "$original" | cmp - "$receipt" >/dev/null || exit 73
    "$flush" d "$volume"
    value=$(read_value) || exit 74
    if [ "$value" != "$original" ] && [ "$value" != disable ]; then exit 73; fi
    if [ "$action" = install ]; then set -- change "$value" disable
    else set -- change "$value" "$original"; fi
fi
[ "$2" = "$value" ] || { printf '%s\n' "Expected $2, found $value" >&2; exit 73; }
if [ "$3" != "$value" ]; then
    case "$3" in
        absent) printf '%s\n' "$key" > "$store/remove" ;;
        *) if [ "$value" = absent ]; then
               printf '%s=%s\n' "$key" "$3" > "$store/add"
           else
               printf '%s\n' "$3" > "$store/keys/$key"
           fi ;;
    esac
    [ "$(read_value)" = "$3" ] || exit 74
fi
# A prior write may have reached sysfs before its commit completed.
# An explicit change also commits a matching value; read stays write-free.
printf '\n' > "$store/commit"
[ "$(read_value)" = "$3" ] || exit 74
if [ "$action" = uninstall ]; then
    rm "$receipt"
    "$flush" d "$volume"
fi
printf '%s\n' "$3"
