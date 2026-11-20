#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Getty supplies the physical console and session. This optional owner console
# changes interactive access only; kernel and diagnostic logging stay intact.
printf '\nOpen Connect owner console (root)\n'
exec /bin/sh -l
