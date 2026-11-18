#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copy authored files verbatim. The only generated text is checksum data.
set -eu
out=$1
case "$out" in /*) ;; *) out=$PWD/$out ;; esac
test -f "$out/receiver" || { echo 'Build with make release.' >&2; exit 1; }
test ! -e "$out/usb" && test ! -L "$out/usb" || { echo 'Choose a fresh OUT directory.' >&2; exit 1; }
mkdir "$out/usb"
# Select only the two authored triggers, never editor files or local captures.
set -- cmu/installer/usb-root/*.up
test "$#" -eq 1 && test -f "$1" && test ! -L "$1"
cp "$1" cmu/installer/usb-root/jci-autoupdate "$out/usb/"
package=$out/usb/open-connect
mkdir "$package"
for file in run.sh session.sh loader.js dialog.js usb-preview.js; do
    cp "cmu/installer/$file" "$package/$file"
done
cp "$out/receiver" "$package/receiver"
cp LICENSE "$package/LICENSE"
cp cmu/installer/KENATIA-LICENSE "$package/KENATIA-LICENSE"
(
    cd "$package"
    for file in session.sh loader.js dialog.js usb-preview.js receiver; do
        digest=$(openssl dgst -sha256 < "$file")
        printf '%s  %s\n' "${digest##* }" "$file"
    done > payload.sha256
)
# ZIP receives literal paths. In particular, never evaluate the .up filename.
archive=$out/open-connect-usb-preview.zip
test ! -e "$archive" && test ! -L "$archive"
(cd "$out/usb" && zip -q -X -r "$archive" .)
digest=$(openssl dgst -sha256 < "$archive")
printf '%s  %s\n' "${digest##* }" open-connect-usb-preview.zip > "$out/SHA256SUMS"
printf '%s\n' "$archive"
