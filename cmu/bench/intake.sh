#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Read-only replacement-CMU inventory. Send stdout to a private host file.
# Run through an already authenticated transport with an external deadline.
set -u
export LC_ALL=C
export PATH=/usr/bin:/bin:/usr/sbin:/sbin

test -r /jci/version.ini || { echo 'Not a readable Mazda CMU filesystem.' >&2; exit 64; }
incomplete=0
read_file() {
    printf '\n[%s]\n' "$1"
    if test -r "$1"; then
        cat "$1" || { echo READ_FAILED; incomplete=1; }
        printf '\n'
    else
        echo UNAVAILABLE
        incomplete=1
    fi
}

printf '%s\n' 'Open Connect bench intake: observations only, no support verdict'
id || incomplete=1
uname -a || incomplete=1
boot=$(cat /proc/sys/kernel/random/boot_id) || exit 74
printf 'boot_start=%s\n' "$boot"
read_file /proc/uptime
printf '\n[firmware identity]\n'
awk '/^JCI_(OEM_PART_NUMBER|SW_PART_NUMBER|SW_VER|SW_VER_PATCH|SW_FLAVOR|CUSTOM_HARDWARE)=/' /jci/version.ini || incomplete=1
read_file /proc/mounts
read_file /sys/class/gpio/DI_TP1056/value
read_file /sys/class/gpio/DI_TP1029/value
read_file /sys/class/gpio/ACC_Sense/value

printf '\n[touch setting]\n'
key=/sys/class/nvram/nv-config/keys/lvds_speed_restriction
if test -r "$key"; then
    read_file "$key"
elif test -d "${key%/*}" && test -r "${key%/*}" && test -x "${key%/*}" &&
     test ! -e "$key" && test ! -L "$key"; then
    echo absent
else
    echo UNAVAILABLE
    incomplete=1
fi

printf '\n[file SHA-256 and metadata: mode uid gid size]\n'
while IFS= read -r path; do
    if test ! -f "$path" || test ! -r "$path"; then
        printf 'UNAVAILABLE %s\n' "$path"
        incomplete=1
        continue
    fi
    digest=$(openssl dgst -sha256 < "$path") || { incomplete=1; printf 'HASH_FAILED %s\n' "$path"; continue; }
    digest=${digest##* }
    case "$digest" in ''|*[!a-f0-9]*) incomplete=1; printf 'HASH_FAILED %s\n' "$path"; continue;; esac
    test "${#digest}" -eq 64 || { incomplete=1; printf 'HASH_FAILED %s\n' "$path"; continue; }
    printf '%s  %s\n' "$digest" "$path"
    stat -c '%a %u %g %s' "$path" || incomplete=1
done <<'FILES'
/usr/bin/autostart
/jci/scripts/get_board_type.sh
/jci/sm/sm.conf
/jci/sm/sm_WCP.conf
/jci/mmui/svcjcimmui.so
/jci/mmui/mmui_config.xml
/jci/mmui/uia/libjciuiasystem.so
/jci/lib/libjciuiamgr.so
/jci/gui/index.html
/jci/gui/apps/system/js/systemApp.js
/jci/gui/apps/syssettings/js/syssettingsApp.js
/jci/gui/framework/js/GuiFramework.js
/jci/gui/framework/js/BaseApp.js
/jci/lvds/lvds_service
/bin/busybox
/usr/bin/openssl
/usr/bin/rungetty
/usr/bin/runlogin
/etc/ssh/sshd_config
FILES

printf '\n[service-manager configuration and loaded GUI/native paths]\n'
for name in sm jci opera; do
    pids=$(pidof "$name") || pids=
    if test -z "$pids"; then printf 'NOT_RUNNING %s\n' "$name"; continue; fi
    for pid in $pids; do
        case "$pid" in ''|*[!0-9]*) incomplete=1; continue;; esac
        printf 'process=%s pid=%s exe=' "$name" "$pid"
        readlink "/proc/$pid/exe" || incomplete=1
        # A process can exit during collection; preserve that failure, not a
        # claim that absent mappings prove the original module was loaded.
        tr '\000' ' ' < "/proc/$pid/cmdline" || incomplete=1
        printf '\n'
        awk '/\/jci\/mmui\/|\/jci\/lib\/libjciuiamgr|\/tmp\/open-connect\//' "/proc/$pid/maps" || incomplete=1
    done
done

printf '\n[available command paths; options still need checking]\n'
for name in openssl timeout flock tcpsvd readlink stat md5sum dd awk sed head; do
    command -v "$name" || { printf 'UNAVAILABLE %s\n' "$name"; incomplete=1; }
done
end=$(cat /proc/sys/kernel/random/boot_id) || exit 74
printf '\nboot_end=%s\n' "$end"
test "$boot" = "$end" || { echo BOOT_CHANGED; exit 75; }
if test "$incomplete" -ne 0; then echo INTAKE_INCOMPLETE; exit 74; fi
echo INTAKE_COMPLETE
