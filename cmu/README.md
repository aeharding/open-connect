# CMU code

This directory contains the code installed or run on the head unit. Host bench
instrumentation lives in `tooling/open_connect/` and is never installed here.

`bench/intake.sh` collects read-only observations from an authenticated replacement
CMU. It is bench instrumentation and is excluded from the release bundle. See the
[v74 porting and intake record](../docs/cmu/firmware74.md) for its use and limits.

## Standalone installer

| Files in `installer/` | Responsibility |
| --- | --- |
| `run.sh`, `session.sh`, `loader.js` | Validate and stage USB files in RAM, then launch the authored UI in Mazda's existing browser |
| `api.c`, `service.sh` | A bounded local POST parser under BusyBox `tcpsvd`; session-token validation and service ownership |
| `runtime.js`, `dialog.js`, `settings.js` | One command contract, Mazda dialogs and native Settings pages |
| `backend.sh`, `transaction.sh`, `state.sh` | Install, preferences, complete uninstall and interrupted-operation reconciliation |
| `firmware.sh`, `mmui.S`, `intro.js`, `system-route.js` | Exact v74 guards and composition from this unit's saved originals |
| `startup-hook.sh`, `boot.sh`, `ignition.sh` | Select a complete RAM configuration before Mazda's normal services and bound repeated attempts |
| `wireless.sh`, `wireless-device.awk` | A finite pre-Device-Manager RAM configuration step for native wireless availability |
| `services-sm.awk` | One selected SM composer for Pandora, native wireless arguments and the experimental Android Auto leaf suppression |

The browser sends `POST /control` to `127.0.0.1:35555`, with `Content-Type:
text/plain` and body `token|revision|operation|arg0|arg1|arg2`. Missing arguments
are `-`. Responses are JSON. The 32-character session token is data supplied by
the loader or a meta element in the privately composed index. The revision binds
the current snapshot; pending recovery uses its unique transaction revision.
Allowed operations are `status`, `install`, `set`, `uninstall`, `recover`,
`restart` and `dismiss`. No shell commands or paths come from browser input.

The only authoritative durable operation/startup record is
`/tmp/mnt/data_persist/open-connect/record`. It references immutable originals,
packages and before/after snapshots. A prepared record is flushed before target
writes. Recovery accepts only the prepared before/after values; unknown later
changes stop the operation. Checked file and directory flushes precede commit.

After verified restoration, the record enters `purge`. The RAM backend deletes
the persistent tree, retaining that record until every other entry is gone.
USB recovery can finish a partial purge or remove its final empty directory.
No installer files or backups remain after successful uninstall. The retired
checkpoint slot and an always-false `undo` response field only allow handoff
from v0.2.0-dev.1; there is no Undo command. Its already-removed installations
offer Uninstall on a new USB to discard their retained files.

Startup integration, touchscreen NVRAM and optional developer login/SSH settings
change in place, with verified originals retained for uninstall.
The native libraries, service configuration, index and paired JavaScript are
composed privately and copied into a fixed RAM directory for the selected boot.
Update and uninstall leave that boot's mapped native bytes intact until restart.
The root filesystem is returned to read-only after startup-file publication.

Wireless selection changes service arguments in the selected RAM profile. After
VBS renders its normal Device Manager XML, one bounded process changes only its
two Wi-Fi capability values before releasing Device Manager initialization.
The physical master XML, board detection, GPS and native modules stay original.
Failure preserves the generated XML and releases ordinary initialization; an
ephemeral applied value contributes to the existing status response. Preferences
remain in the same immutable snapshot and authoritative durable record.

`features/touch/setting.sh` compares the expected NVRAM value before changing and
committing it. It preserves the distinction between absent, enable and disable.
`features/disclaimer/` contains the independently authored native bypass.
`startup/flush.c` provides checked file/directory durability. Its generic
publication template is bench instrumentation for native file trials.

`make release` uses standard Clang/LLD/llvm-objcopy and Make/shell packaging.
Authored shell and JavaScript files are copied unchanged; only compiled assets
and data manifests are generated. No OEM firmware or host Python is bundled.
See [Quick start](../docs/usb-installer.md) for owner instructions and
[Build and test the installer](../docs/installer-development.md) for backend behavior.

Maintenance status distinguishes the running package’s `version` from the
verified current snapshot’s `installedVersion`. The USB prompt uses these for
To and From respectively; an unavailable installed identity is shown explicitly,
never inferred from the staged client.
