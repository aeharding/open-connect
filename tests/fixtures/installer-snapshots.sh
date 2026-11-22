# SPDX-License-Identifier: AGPL-3.0-or-later
# Readable scalar choices for physical-adapter fixtures. Invoke the actual
# seven-argument writer with one canonical preferences payload; never installed.
fixture_snapshot() (
    local prefs= package=$2 dependencies=${7:--}
    if test "$dependencies" = /dev/null; then dependencies=-; fi
    if test "$package" != -; then
        prefs=$(printf 'OC2\nbase=%s\nmetadata=%s\nnvram=%s\npackage=%s\nservice.android-auto=1\nservice.pandora=%s\ntouch=%s\nwarning=%s\nwireless=%s' \
            "${10:-0}" "$6" "$5" "$package" "${9:-1}" "$3" "$4" "${11:-0}")
    fi
    snapshot_create "$1" "$package" "$5" "$6" "$dependencies" "${8:--}" "$prefs"
)
