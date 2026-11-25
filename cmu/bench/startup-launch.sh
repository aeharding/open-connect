#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Finite local boot observer. Only the installation lives on flash; output is RAM.
set -eu
umask 077
export LC_ALL=C PATH=/usr/bin:/bin:/usr/sbin:/sbin
D=/tmp/mnt/data_persist/oc-bench-startup
R=/tmp/oc-bench-startup
test "$(id -u)" = 0
test "$(readlink -f "$D")" = "$D"
test "$(stat -c '%a:%u:%g' "$D")" = 700:0:0
# Claim once before starting either finite bench observer.
mkdir "$R"
read -r boot < /proc/sys/kernel/random/boot_id
# Match silent-ui-v1 before the one-shot CarPlay focus request, on every cohort.
# This child never delays Service Manager and never retries a mutating request.
(
    ulimit -f 128
    set +e
    timeout -t 25 sh -s -- "$boot" > "$R/audio-profile" 2> "$R/audio-stderr" <<'OC_AUDIO'
set -eu
boot=$1
bus=unix:path=/tmp/dbus_hmi_socket
service=com.xsembedded.service.AudioManagement
call() { dbus-send --address="$bus" --dest="$1" --type=method_call --print-reply --reply-timeout=1000 "$2" "$3" "${4:-}" "${5:-}"; }
# Keep empty arguments out of DBus methods that take none.
owner() { dbus-send --address="$bus" --dest=org.freedesktop.DBus --type=method_call --print-reply --reply-timeout=1000 /org/freedesktop/DBus org.freedesktop.DBus.GetNameOwner "string:$service"; }
scalar() { sed -n 's/^   string "\(.*\)"$/\1/p'; }
attempt=0
while ! reply=$(owner 2>/dev/null); do
    attempt=$((attempt+1)); test "$attempt" -le 20
    sleep 1
done
o=$(printf '%s\n' "$reply" | scalar)
printf '%s\n' "$o" | awk 'END{exit !(NR==1&&$0~/^:[0-9]+[.][0-9]+$/)}'
request() { call "$o" /com/xse/service/AudioManagement/HmiMode com.xsembedded.ServiceProvider.Request "string:$1" "string:$2"; }
read -r started rest < /proc/uptime
before=$(request enableStatus '{}' | scalar)
case "$before" in
    '{"enable":false}') test "$(request enable '{"enable":true}' | scalar)" = '{}';;
    '{"enable":true}') ;;
    *) exit 76;;
esac
after=$(request enableStatus '{}' | scalar)
test "$after" = '{"enable":true}'
test "$(owner | scalar)" = "$o"
read -r current < /proc/sys/kernel/random/boot_id
test "$current" = "$boot"
read -r ended rest < /proc/uptime
printf 'AUDIO_PROFILE|silent-ui-v1|%s|%s|%s|%s|%s|%s\n' "$boot" "$o" "$before" "$after" "$started" "$ended"
OC_AUDIO
    code=$?
    printf '%s\n' "$code" > "$R/audio-exit"
) &
# Optional bench fixture: an old installer USB must not replace the measured
# candidate's listener. Bind deauthorization to this device and a private serial.
quarantine=-
policy=$D/usb-quarantine-serial
if test -e "$policy" || test -L "$policy"; then
    test -f "$policy" && test ! -L "$policy" && test "$(readlink -f "$policy")" = "$policy"
    test "$(stat -c '%a:%u:%g' "$policy")" = 600:0:0
    read -r expected_serial < "$policy"
    case "$expected_serial" in ''|*[!0-9a-fA-F]*) exit 64;; esac
    usb=/sys/bus/usb/devices/1-1.1
    # USBMGR authorizes this device after stage_1. This detached observer may
    # wait finitely; Service Manager is never held by the fixture guard.
    attempts=0
    while :; do
        if test -r "$usb/idVendor"; then
            read -r vendor < "$usb/idVendor"; read -r product < "$usb/idProduct"
            test "$vendor:$product" = 0781:55a9
            read -r authorized < "$usb/authorized"
            if test "$authorized" = 1; then break; fi
        fi
        attempts=$((attempts+1)); test "$attempts" -le 25
        sleep 1
    done
    read -r vendor < "$usb/idVendor"; read -r product < "$usb/idProduct"
    read -r actual_serial < "$usb/serial"
    test "$vendor:$product:$actual_serial" = "0781:55a9:$expected_serial"
    printf '0\n' > "$usb/authorized"
    read -r authorized < "$usb/authorized"
    test "$authorized" = 0
    quarantine=$(openssl dgst -sha256 < "$policy"); quarantine=${quarantine##* }
fi
ulimit -f 8192
token=$(printf '%s' "$boot" | tr -d -)
test "${#token}" = 32
sha() { value=$(openssl dgst -sha256 < "$1"); printf '%s\n' "${value##* }"; }
expected=$(awk '$2=="metrics.sh"{print $1}' "$D/files.sha256")
test "${#expected}" = 64
test "$(sha "$D/metrics.sh")" = "$expected"
{
    printf 'BOOT|%s\nMETRICS_SHA|%s\nLAUNCH_SHA|%s\n' "$boot" "$expected" "$(sha "$D/startup-launch.sh")"
    printf 'HOOK_SHA|%s\nSTART_UPTIME|' "$(sha /jci/scripts/stage_1.sh)"
    cat /proc/uptime
    printf 'USB_QUARANTINE|1-1.1|0781:55a9|%s\n' "$quarantine"
} > "$R/metadata"
set +e
timeout -t 190 sh "$D/metrics.sh" 180 1 "$token" > "$R/trace.raw" 2> "$R/stderr"
code=$?
set -e
printf '%s\n' "$code" > "$R/exit.tmp"
mv "$R/exit.tmp" "$R/exit"
exit "$code"
