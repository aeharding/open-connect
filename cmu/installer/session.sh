#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
set -eu
work=$1
source=$2
runtime=
token=
navigate() {
    dbus-send --address=unix:path=/tmp/dbus_hmi_socket --type=method_call \
        --print-reply --reply-timeout=3000 --dest=com.jci.OPERA_IHU_PRIMARY \
        /com/jci/OPERA_IHU_PRIMARY com.jci.opera_IHU_PRIMARY.Navigate "string:$1" >/dev/null
}
cleanup() {
    if test -n "$token"; then
        navigate "javascript:void((function(){if(window.OpenConnect)OpenConnect.cancelUSB('$token');if(window.__ocUSBLoading&&window.__ocUSBLoading.token==='$token')window.__ocUSBLoading.cancel();var s=document.getElementById('oc-usb-loader');if(s&&s.ocToken==='$token')s.parentNode.removeChild(s);}()))" || :
    fi
    if test -n "$runtime"; then sh "$runtime/service.sh" stop || :; fi
    rm -f "$work"/*
    rmdir "$work"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
runtime=$(sh "$work/service.sh")
token=$(cat "$runtime/token")
test "${#token}" -eq 32 || exit 1
case "$token" in *[!a-f0-9]*) exit 1;; esac
logger -t open-connect "OCUSB|$token|start"
navigate "javascript:void(setTimeout(function(){if(document.getElementById('oc-usb-loader'))return;utility.loadScript('../..$runtime/loader.js',{id:'oc-usb-loader',ocToken:'$token'},function(){});},0))"
count=0
while test "$count" -lt 300; do
    test ! -f "$runtime/closed" || exit 0
    test -f "$source/run.sh" || exit 0
    test "$(readlink -f /tmp/open-connect/runtime)" = "$runtime" || exit 0
    count=$((count+1))
    sleep 1
done
