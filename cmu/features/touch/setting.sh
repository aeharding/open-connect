#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Firmware 74.00.324A NA installer primitive. The caller saves the pre-install
# value before calling change and retains it for uninstall.
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
    read:1) ;;
    change:3) valid "$2" && valid "$3" || exit 64 ;;
    *) exit 64 ;;
esac
awk '
    $0 == "JCI_SW_VER=\"MAZ_CMU-150_74.00.324\"" {v++}
    $0 == "JCI_SW_VER_PATCH=\"A\"" {p++}
    $0 == "JCI_SW_FLAVOR=\"cmu150_NA\"" {f++}
    END {exit !(v==1 && p==1 && f==1)}
' /jci/version.ini || exit 65
[ "$(md5sum < /jci/lvds/lvds_service)" = '1d3e74362d4a97814a9f0fb316ff583f  -' ] || exit 65

if [ "$1" = change ]; then
    # Serialize Open Connect operations. Other services may also own NVRAM.
    lock=/tmp/oc-lvds-setting.lock
    if [ ! -e "$lock" ] && [ ! -L "$lock" ]; then
        (umask 077; set -C; : > "$lock") || exit 75
    fi
    [ -f "$lock" ] && [ ! -L "$lock" ] && [ "$(readlink -f "$lock")" = "$lock" ] || exit 75
    exec 8<>"$lock"
    flock -n -x 8 || exit 75
fi
value=$(read_value) || exit 74
valid "$value" || exit 65
if [ "$1" = read ]; then printf '%s\n' "$value"; exit 0; fi
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
printf '%s\n' "$3"
