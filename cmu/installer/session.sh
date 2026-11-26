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
    if test "${1:-}" != locked; then service_lock usb; fi
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
entry_live() {
    test ! -f "$runtime/closed" && test -f "$source/run.sh" &&
        test "$(readlink -f /tmp/open-connect/usb-runtime)" = "$runtime"
}
cleanup() {
    # Native liveness polling closes this popup. Teardown never navigates Opera.
    exec 9>&-
    if test -n "$runtime" && test -d "$runtime"; then
        : > "$runtime/closed"
        sh "$runtime/usb-service.sh" stop || :
    fi
    rm -f "$work"/*
    rmdir "$work"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if post_restart; then exit 0; fi
runtime=$(sh "$work/usb-service.sh")
# Done can finish while the replacement listener is being staged. Keep that
# listener for installed Settings, but do not replace its already-owned UI.
if post_restart; then exit 0; fi
# Keep the listener record compatible with older installed clients/services.
# The staged module checks the actual child and owned socket, not a claimed port.
. "$runtime/service.sh"
read -r pid start served extra < /tmp/open-connect/usb-listener
test "$served" = "$runtime" && test -z "$extra" || exit 1
if service_owns_listener "$pid" "$start" "$runtime" 15557; then port=15557
else exit 1; fi
token=$(cat "$runtime/token")
test "${#token}" -eq 32 || exit 1
case "$token" in *[!a-f0-9]*) exit 1;; esac
entry_live || exit 0
logger -t open-connect "OCUSB|$token|start"
if test -f /tmp/open-connect/feature/runtime.js &&
    grep -F -q 'OC_USB_OFFER_V1:' /tmp/open-connect/feature/runtime.js; then
    R=/tmp/open-connect
    . "$work/state.sh"
    service_lock usb
    if post_restart locked; then exit 0; fi
    entry_live || exit 0
    service_owns_listener "$pid" "$start" "$runtime" 15557 || exit 1
    name=${runtime##*/}
    test "${#name}" -eq 14 || exit 1
    case "$name" in session-??????) ;; *) exit 1;; esac
    case "$name" in *[!a-zA-Z0-9-]*) exit 1;; esac
    # Discovery is offered only after final retained-stick/ownership checks,
    # serialized with Done. An older runner or suppressed session offers nothing.
    (set -C; printf '%s|%s\n' "$name" "$token" > "$runtime/.offer")
    mv "$runtime/.offer" "$runtime/offer"
    exec 9>&-
else
    # Stock and older installed releases have no browser-side USB receiver.
    entry_live || exit 0
    # Only node/deadline ownership must precede script delivery. The static
    # loader/popup take over cancellation; Mazda pairs evaluation with onload.
    navigate "javascript:void(setTimeout(function(){var old=window.__ocUSBLoading;if(old&&old.role==='usb-discovery'){if(old.token==='$token')return;old.cancel();}if(window.__ocUSBLoading)return;old=document.getElementById('oc-maintenance-loader');if(old&&old.parentNode)old.parentNode.removeChild(old);var entry,timer,hold={role:'usb-discovery',token:'$token',owner:window.OpenConnect,cancel:function(){clearTimeout(timer);if(entry&&entry.parentNode)entry.parentNode.removeChild(entry);if(window.__ocUSBLoading===hold)delete window.__ocUSBLoading;hold.owner=null;if(hold.stop){var stop=hold.stop;hold.stop=null;stop();}}};window.__ocUSBLoading=hold;timer=setTimeout(hold.cancel,65000);utility.loadScript('../..$runtime/loader.js',{id:'oc-maintenance-loader',ocToken:'$token',ocPort:$port,ocDiscovery:hold},function(){if(entry&&entry===document.getElementById('oc-maintenance-loader')&&typeof OpenConnectUSBStart==='function')OpenConnectUSBStart(entry);});entry=document.getElementById('oc-maintenance-loader');},0))"
fi
count=0
while test "$count" -lt 300; do
    test ! -f "$runtime/closed" || exit 0
    test -f "$source/run.sh" || exit 0
    test "$(readlink -f /tmp/open-connect/usb-runtime)" = "$runtime" || exit 0
    count=$((count+1))
    sleep 1
done
