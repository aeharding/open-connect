#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# One temporary v74 bench hook, with independent exact-content restoration.
set -eu
umask 077
export LC_ALL=C PATH=/usr/bin:/bin:/usr/sbin:/sbin
D=/tmp/mnt/data_persist/oc-bench-startup
T=/jci/scripts/stage_1.sh
H=/jci/scripts/.oc-bench-stage1-original
W=/jci/scripts/.oc-bench-stage1-new
O=2ec71fc955d0107a6e90d1ab4e6f00c9438b56d3e621ef018d57c8ef07bfae7f
sha() { value=$(openssl dgst -sha256 < "$1"); printf '%s\n' "${value##* }"; }
file() { test -f "$1" && test ! -L "$1" && test "$(readlink -f "$1")" = "$1"; }
absent() { test ! -e "$1" && test ! -L "$1"; }
identity() { stat -c '%d:%i:%a:%u:%g:%s' "$1"; }
root_mode() { awk '$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"{n++;m=$4} END{if(n!=1)exit 1;print m}' /proc/mounts; }
verify() (
    cd "$1"
    test "$(wc -l < files.sha256)" -eq 5
    for name in startup-hook.sh startup-launch.sh startup-profile.sh metrics.sh flush; do
        file "$1/$name"
        expected=$(awk -v n="$name" '$2==n{print $1}' files.sha256)
        test "${#expected}" = 64
        test "$(sha "$name")" = "$expected"
    done
)
test "$(id -u)" = 0
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
     $0=="JCI_SW_VER_PATCH=\"A\""{p++}
     $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
     END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
test "$(root_mode)" = ro,noatime
file "$T"
action=$1
case "${1:-}" in
install)
    test "${2:-}" = "$(cat /proc/sys/kernel/random/boot_id)"
    absent "$D" && absent "$H" && absent "$W"
    test "$(sha "$T")" = "$O"
    test "$(stat -c '%a:%u:%g:%s:%h' "$T")" = 775:1000:1000:11:1
    S=$(readlink -f "$(dirname "$0")")
    case "$S" in /tmp/oc-dev-startup-*) ;; *) exit 64;; esac
    verify "$S"
    mkdir "$D"
    chmod 700 "$D"
    for name in startup-hook.sh startup-launch.sh startup-profile.sh metrics.sh flush files.sha256; do
        cp "$S/$name" "$D/$name"
        chmod 600 "$D/$name"
    done
    chmod 700 "$D/flush"
    cp -p "$T" "$D/stage_1.original"
    identity "$T" > "$D/original.identity"
    verify "$D"
    test "$(sha "$D/stage_1.original")" = "$O"
    for name in startup-hook.sh startup-launch.sh startup-profile.sh metrics.sh flush files.sha256 stage_1.original original.identity; do
        "$D/flush" f "$D/$name"
    done
    "$D/flush" d "$D"
    "$D/flush" d "${D%/*}"
    # Prove the independent restore entry is usable before changing the target.
    sh "$D/startup-profile.sh" --check
    ;;
--check|--restore|--enable)
    test "$(readlink -f "$D")" = "$D"
    test "$(stat -c '%a:%u:%g' "$D")" = 700:0:0
    verify "$D"
    file "$D/stage_1.original"
    test "$(sha "$D/stage_1.original")" = "$O"
    current=$(sha "$T")
    if test "$current" = "$O"; then
        test "$(identity "$T")" = "$(cat "$D/original.identity")"
        if ! absent "$H"; then
            file "$H"
            test "$(identity "$H")" = "$(cat "$D/original.identity")"
            test "$(stat -c '%h' "$T")" = 2
        else
            test "$(stat -c '%h' "$T")" = 1
        fi
    else
        test "$current" = "$(sha "$D/startup-hook.sh")"
        test "$(stat -c '%a:%u:%g:%h' "$T")" = 775:1000:1000:1
        file "$H"
        test "$(sha "$H")" = "$O"
        test "$(identity "$H")" = "$(cat "$D/original.identity")"
        test "$(stat -c '%h' "$H")" = 1
    fi
    if test "$1" = --check; then echo STARTUP_RECOVERY_READY; exit; fi
    if test "$1" = --enable; then
        test "${2:-}" = "$(cat /proc/sys/kernel/random/boot_id)"
        test "$current" = "$O"
        absent "$H" && absent "$W"
        action=install
    fi
    ;;
*) exit 64;;
esac
finish() {
    code=$?
    trap - EXIT HUP INT TERM
    timeout -t 8 /bin/busybox mount -i -n -t relfs -o remount,ro,noatime /dev/ffx01p1 / || code=1
    test "$(root_mode)" = ro,noatime || code=1
    exit "$code"
}
trap finish EXIT
trap 'exit 1' HUP INT TERM
timeout -t 8 /bin/busybox mount -i -n -t relfs -o remount,rw,noatime /dev/ffx01p1 /
if test "$action" = install; then
    test "$(identity "$T")" = "$(cat "$D/original.identity")"
    test "$(sha "$T")" = "$O"
    ln "$T" "$H"
    "$D/flush" d "${T%/*}"
    cp "$D/startup-hook.sh" "$W"
    chmod 775 "$W"
    chown 1000:1000 "$W"
    test "$(sha "$W")" = "$(sha "$D/startup-hook.sh")"
    "$D/flush" f "$W"
    test "$(identity "$T")" = "$(cat "$D/original.identity")"
    test "$(sha "$T")" = "$O"
    mv "$W" "$T"
    "$D/flush" f "$T"
    "$D/flush" d "${T%/*}"
    echo STARTUP_HOOK_INSTALLED
else
    if test "$(sha "$T")" != "$O"; then
        test "$(sha "$T")" = "$(sha "$D/startup-hook.sh")"
        test "$(sha "$H")" = "$O"
        mv "$H" "$T"
    elif ! absent "$H"; then
        # An interrupted install may have made only the original hardlink.
        test "$(identity "$H")" = "$(identity "$T")"
        rm "$H"
    fi
    "$D/flush" f "$T"
    "$D/flush" d "${T%/*}"
    test "$(sha "$T")" = "$O"
    test "$(identity "$T")" = "$(cat "$D/original.identity")"
    test "$(stat -c '%h' "$T")" = 1
    echo STARTUP_HOOK_RESTORED_RESTART_REQUIRED
fi
