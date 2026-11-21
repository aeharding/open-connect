#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copy authored files verbatim. The only generated text is checksum data.
set -eu
out=$1
case "$out" in /*) ;; *) out=$PWD/$out;; esac
test -f "$out/api" || { echo 'Build with make release.' >&2; exit 1; }
test ! -e "$out/usb" && test ! -L "$out/usb" || { echo 'Choose a fresh OUT directory.' >&2; exit 1; }
mkdir "$out/usb"
set -- cmu/installer/usb-root/*.up
test "$#" -eq 1 && test -f "$1" && test ! -L "$1"
cp "$1" cmu/installer/usb-root/jci-autoupdate "$out/usb/"
package=$out/usb/open-connect
mkdir "$package"
for file in run.sh session.sh service.sh loader.js runtime.js dialog.js settings.js \
    backend.sh state.sh transaction.sh firmware.sh access.sh console.sh boot.sh startup-hook.sh ignition.sh \
    intro.js system-route.js wireless.sh wireless-sm.awk wireless-device.awk VERSION KENATIA-LICENSE; do
    cp "cmu/installer/$file" "$package/$file"
done
cp cmu/features/touch/setting.sh "$package/touch.sh"
cp cmu/features/disclaimer/layout.txt "$package/layout.txt"
for file in api flush native.bin branch.bin sizes.bin layout.bin mmui-path.bin mmui-sizes.bin mmui-length.bin mmui-pointer.bin mmui-count-pointer.bin; do
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
