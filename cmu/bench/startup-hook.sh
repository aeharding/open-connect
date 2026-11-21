#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Temporary bench instrumentation; the supported OEM stage_1 is empty.
# Never hold up Service Manager, including when the bench payload is absent.
D=/tmp/mnt/data_persist/oc-bench-startup
if test -f "$D/startup-launch.sh" && test ! -L "$D/startup-launch.sh"; then
    /usr/bin/setsid /bin/sh "$D/startup-launch.sh" </dev/null >/dev/null 2>&1 &
fi
exit 0
