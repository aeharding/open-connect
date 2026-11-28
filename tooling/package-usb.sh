#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copy authored files verbatim. The only generated text is checksum data.
set -eu
out=$1
case "$out" in /*) ;; *) out=$PWD/$out;; esac
test -f "$out/api" || { echo 'Build with make release.' >&2; exit 1; }
# Each staged inode has its own tmpfs page budget; spare space is not transferable.
for limit in dialog.js:8192 runtime.js:16384 maintenance.js:20480 settings.js:28672 carplay.js:4096 loader.js:4096 service.sh:16384 preferences.awk:8192; do
    name=${limit%:*}; bytes=${limit#*:}
    test "$(wc -c < "cmu/installer/$name")" -le "$bytes" || {
        echo "$name exceeds its RAM page budget ($bytes bytes)." >&2; exit 1;
    }
done
for limit in touch-disable.so:4096 flush:4096 api:81920 install:81920 boot-select:36864 ignition:4096; do
    name=${limit%:*}; bytes=${limit#*:}
    test "$(wc -c < "$out/$name")" -le "$bytes" || {
        echo "$name exceeds its RAM page budget ($bytes bytes)." >&2; exit 1;
    }
done
test ! -e "$out/usb" && test ! -L "$out/usb" || { echo 'Choose a fresh OUT directory.' >&2; exit 1; }
mkdir "$out/usb"
set -- cmu/installer/usb-root/*.up
test "$#" -eq 1 && test -f "$1" && test ! -L "$1"
cp "$1" cmu/installer/usb-root/jci-autoupdate "$out/usb/"
package=$out/usb/open-connect
mkdir "$package"
for file in run.sh session.sh service.sh usb-service.sh loader.js runtime.js maintenance.js dialog.js settings.js carplay.js \
    console.sh startup-hook.sh startup-join.sh \
    system-hook.js base-logging.js defer-gap2.sh defer-nav.sh ui-profile.awk ui-modules.tsv wireless.sh wireless-device.awk preferences.awk services.tsv sm-profile.awk VERSION KENATIA-LICENSE; do
    cp "cmu/installer/$file" "$package/$file"
done
cp cmu/features/disclaimer/layout.txt "$package/layout.txt"
for file in api install flush boot-select ignition touch-disable.so native.bin branch.bin sizes.bin layout.bin vui-path.bin mmui-path.bin mmui-sizes.bin mmui-length.bin mmui-pointer.bin mmui-count-pointer.bin; do
    cp "$out/$file" "$package/$file"
done
cp LICENSE "$package/LICENSE"
(
    cd "$package"
    for file in *; do
        test "$file" != files.sha256 || continue
        digest=$(openssl dgst -sha256 < "$file")
        printf '%s  %s\n' "${digest##* }" "$file"
    done > files.sha256
)
version=$(cat "$package/VERSION")
case "$version" in ''|*[!a-zA-Z0-9.-]*) exit 1;; esac
name=open-connect-$version-usb.zip
archive=$out/$name
test ! -e "$archive" && test ! -L "$archive"
(cd "$out/usb" && zip -q -X -r "$archive" .)
digest=$(openssl dgst -sha256 < "$archive")
printf '%s  %s\n' "${digest##* }" "$name" > "$out/SHA256SUMS"
printf '%s\n' "$archive"
