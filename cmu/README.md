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
| `backend.sh`, `transaction.sh`, `state.sh` | Install, preferences, uninstall, undo and interrupted-operation reconciliation |
| `firmware.sh`, `mmui.S`, `intro.js`, `system-route.js` | Exact v55 guards and composition from this unit's saved originals |
| `startup-hook.sh`, `boot.sh`, `ignition.sh` | Select a complete RAM configuration before Mazda's normal services and bound repeated attempts |

The browser sends `POST /control` to `127.0.0.1:35555`, with `Content-Type:
text/plain` and body `token|revision|operation|arg0|arg1|arg2`. Missing arguments
are `-`. Responses are JSON. The 32-character session token is data supplied by
the loader or a meta element in the privately composed index. The revision binds
the current snapshot; pending recovery uses its unique transaction revision.
Allowed operations are `status`, `install`, `set`, `uninstall`, `undo`, `recover`,
`restart` and `dismiss`. No shell commands or paths come from browser input.

The only authoritative durable operation/startup record is
`/tmp/mnt/data_persist/open-connect/record`. It references immutable originals,
packages and before/after snapshots. A prepared record is flushed before target
writes. Recovery accepts only the prepared before/after values; unknown later
changes stop the operation. Checked file and directory flushes precede commit.

Only the startup integration and Mazda's touchscreen NVRAM value change in place.
The native libraries, service configuration, index and paired JavaScript are
composed privately and copied into a fixed RAM directory for the selected boot.
Update and uninstall leave that boot's mapped native bytes intact until restart.
The root filesystem is returned to read-only after startup-file publication.

`features/touch/setting.sh` compares the expected NVRAM value before changing and
committing it. It preserves the distinction between absent, enable and disable.
`features/disclaimer/` contains the independently authored native bypass.
`startup/` also contains the existing host-driven trial helpers; they are bench
instrumentation, not the product's persistence policy.

`make release` uses standard Clang/LLD/llvm-objcopy and Make/shell packaging.
Authored shell and JavaScript files are copied unchanged; only compiled assets
and data manifests are generated. No OEM firmware or host Python is bundled.
See the [USB guide](../docs/usb-installer.md) and [uninstall behavior](../docs/uninstall.md).
