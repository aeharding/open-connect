#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
set -eu
work=$1
source=$2
runtime=
token=
post_restart() (
    trap - EXIT HUP INT TERM
    R=/tmp/open-connect; D=/tmp/mnt/data_persist/open-connect; P=$work
    test -f "$R/selected" && test -f "$R/feature/index.html" || exit 1
    . "$work/state.sh"; . "$work/service.sh"
    service_lock usb
    private_dir "$D" && record_read && test "$R_PHASE" = active || exit 1
    test "$(current_boot_id)" = "$R_BOOT" && test "$(cat "$R/selected")" = "$R_CURRENT" || exit 1
    grep -F -q '<meta name="open-connect-notice" content="installed"' "$R/feature/index.html" || exit 1
    file "$D/packages/$R_BACKEND/files.sha256" &&
        test "$(sha "$D/packages/$R_BACKEND/files.sha256")" = "$R_BACKEND" || exit 1
    test "$(awk '$2!="INSTANCE"{print $1" "$2}' "$work/files.sha256")" = \
        "$(awk '$2!="INSTANCE"{print $1" "$2}' "$D/packages/$R_BACKEND/files.sha256")" || exit 1
    ids=$(service_usb_observe "$R_NOTICE") && id=$(service_usb_source "$source") || exit 1
    case ";$ids" in *";$id;"*) exit 0;; esac
    exit 1
)
navigate() {
    dbus-send --address=unix:path=/tmp/dbus_hmi_socket --type=method_call \
        --print-reply --reply-timeout=3000 --dest=com.jci.OPERA_IHU_PRIMARY \
        /com/jci/OPERA_IHU_PRIMARY com.jci.opera_IHU_PRIMARY.Navigate "string:$1" >/dev/null
}
cleanup() {
    # Done/Cancel already closed their view. A browser navigation here can abort
    # Mazda's next template load. A retired runner must also leave its successor.
    if test -n "$token" && test ! -f "$runtime/closed" &&
        test "$(readlink -f /tmp/open-connect/runtime 2>/dev/null || :)" = "$runtime"; then
        navigate "javascript:void((function(){if(window.OpenConnect)OpenConnect.cancelUSB('$token');if(window.__ocUSBLoading&&window.__ocUSBLoading.token==='$token')window.__ocUSBLoading.cancel();var s=document.getElementById('oc-usb-loader');if(s&&s.ocToken==='$token')s.parentNode.removeChild(s);}()))" || :
    fi
    if test -n "$runtime"; then sh "$runtime/service.sh" stop || :; fi
    rm -f "$work"/*
    rmdir "$work"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if post_restart; then exit 0; fi
runtime=$(sh "$work/service.sh")
# Done can finish while the replacement listener is being staged. Keep that
# listener for installed Settings, but do not replace its already-owned UI.
if post_restart; then exit 0; fi
# Keep the listener record compatible with older installed clients/services.
# The staged module checks the actual child and owned socket, not a claimed port.
. "$runtime/service.sh"
read -r pid start served extra < /tmp/open-connect/listener
test "$served" = "$runtime" && test -z "$extra" || exit 1
if service_owns_listener "$pid" "$start" "$runtime" 35555; then port=35555
elif service_owns_listener "$pid" "$start" "$runtime" 15555; then port=15555
else exit 1; fi
token=$(cat "$runtime/token")
test "${#token}" -eq 32 || exit 1
case "$token" in *[!a-f0-9]*) exit 1;; esac
test ! -f "$runtime/closed" || exit 0
logger -t open-connect "OCUSB|$token|start"
navigate "javascript:void(setTimeout(function(){if(document.getElementById('oc-usb-loader'))return;utility.loadScript('../..$runtime/loader.js',{id:'oc-usb-loader',ocToken:'$token',ocPort:$port},function(){});},0))"
count=0
while test "$count" -lt 300; do
    test ! -f "$runtime/closed" || exit 0
    test -f "$source/run.sh" || exit 0
    test "$(readlink -f /tmp/open-connect/runtime)" = "$runtime" || exit 0
    count=$((count+1))
    sleep 1
done
