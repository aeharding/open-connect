#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Runs from the verified RAM copy. Only the current session can be dismissed.
set -eu
work=$1
source=$2
token=$3
receiver=
port=$((20000 + $$ % 20000))
navigate() {
    dbus-send --address=unix:path=/tmp/dbus_hmi_socket --type=method_call \
        --print-reply --reply-timeout=3000 --dest=com.jci.OPERA_IHU_PRIMARY \
        /com/jci/OPERA_IHU_PRIMARY com.jci.opera_IHU_PRIMARY.Navigate "string:$1" >/dev/null
}
cleanup() {
    navigate "javascript:void((function(){if(window.__ocUSB&&window.__ocUSB.token==='$token')window.__ocUSB.cancel();if(window.__ocUSBLoading&&window.__ocUSBLoading.token==='$token')window.__ocUSBLoading.cancel();}()))" || :
    if test -n "$receiver"; then
        # Re-enumerate the executable before signalling our child.
        if test "$(readlink /proc/$receiver/exe 2>/dev/null)" = "$work/receiver"; then kill "$receiver" 2>/dev/null || :; fi
        wait "$receiver" 2>/dev/null || :
    fi
    rm -f "$work/loader.js" "$work/dialog.js" "$work/usb-preview.js" "$work/session.sh" "$work/receiver" "$work/receiver.log" "$work/payload.sha256"
    rmdir "$work"
    rmdir /tmp/open-connect-usb.lock
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
"$work/receiver" "$port" "$token" 90 > "$work/receiver.log" 2>&1 &
receiver=$!
count=0
until grep -q '^OCHEALTH|listening$' "$work/receiver.log"; do
    count=$((count + 1))
    test "$count" -lt 5 && kill -0 "$receiver" 2>/dev/null || exit 1
    sleep 1
done
# A void javascript URL executes in the original document; it does not replace it.
# Defer loading until Navigate returns; synchronous loads were dropped on v55.
# Relative URLs preserve Opera's file://localhost origin. Keep this generic:
# the payload owns the dialog; this entry only supplies a token and reply port.
navigate "javascript:void(setTimeout(function(){if(window.__ocUSB||document.getElementById('oc-usb-loader'))return;utility.loadScript('../..$work/loader.js',{id:'oc-usb-loader',ocToken:'$token',ocPort:$port},function(){});},0))"
count=0
while test "$count" -lt 90; do
    if grep -q '^OCHEALTH|ready$' "$work/receiver.log"; then
        wait "$receiver"
        receiver=
        logger -t open-connect "OCUSB|$token|closed"
        exit 0
    fi
    test -f "$source/run.sh" || { logger -t open-connect "OCUSB|$token|removed"; exit 0; }
    kill -0 "$receiver" 2>/dev/null || exit 1
    count=$((count + 1))
    sleep 1
done
logger -t open-connect "OCUSB|$token|timeout"
exit 1
