#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# SM's 15-second timeout releases the stage on failure as well as normal exit.
set -eu
flag=/tmp/open-connect/feature/gap2-ready
test ! -e "$flag" && test ! -L "$flag"
/bin/busybox sleep 12
(set -C; printf 'ready\n' > "$flag")
