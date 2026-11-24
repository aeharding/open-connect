#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Independent of projection. SM releases this parent on exit, including timeout.
set -eu
flag=/tmp/open-connect/feature/nav-ready
test ! -e "$flag" && test ! -L "$flag"
/bin/busybox sleep 20
(set -C; printf 'ready\n' > "$flag")
