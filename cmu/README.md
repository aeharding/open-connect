# CMU code

This directory contains the code installed or run on the head unit. Host bench
instrumentation lives in `tooling/open_connect/` and is never installed here.

`bench/intake.sh` collects read-only observations from an authenticated replacement
CMU. It is bench instrumentation and is excluded from the release bundle. See the
[v74 porting and intake record](../docs/cmu/firmware74.md) for its use and limits.

## Standalone installer

| Files in `installer/` | Responsibility |
| --- | --- |
| `run.sh`, `session.sh`, `loader.js`, `usb-service.sh` | Stage verified USB bytes and own one transient maintenance session |
| `api.c`, `service.sh` | A bounded local POST parser under BusyBox `tcpsvd`; separate installed and USB listener ownership |
| `runtime.js`, `dialog.js`, `settings.js` | Boot-selected installed Settings and its native input/page lifecycle |
| `maintenance.js` | Independent USB choices, progress and installed completion; no Settings replacement |
| `backend.sh`, `transaction.sh`, `state.sh` | Install, preferences, complete uninstall and interrupted-operation reconciliation |
| `firmware.sh`, `mmui.S`, `intro.js`, `system-route.js` | Exact v74 guards and composition from this unit's saved originals |
| `startup-hook.sh`, `boot.sh`, `ignition.c` | Select a complete RAM configuration before Mazda's normal services and bound repeated attempts |
| `boot-select.c`, `core/*.c`, `core/oc-core.h` | Modular freestanding C core: seal verified boot inputs, select unchanged snapshots, and safely prune unreachable snapshots |
| `services.tsv`, `preferences.awk`, `sm-profile.awk` | Built-in Services catalog, canonical preferences and one RAM Service Manager composer |
| `wireless.sh`, `wireless-device.awk` | A finite pre-Device-Manager RAM configuration step and narrow native wireless service arguments |

The browser sends `POST /control` to installed port `15555` or transient USB port
`15557` on `127.0.0.1`, with `Content-Type:
text/plain` and body `token|revision|operation|arg0|arg1|arg2`. Missing arguments
are `-`. Responses are JSON. The 32-character session token is data supplied by
the loader or a meta element in the privately composed index. The revision binds
the current snapshot; pending recovery uses its unique transaction revision.
Allowed operations are `status`, `install`, `set`, `uninstall`, `recover`,
`restart`, `dismiss` and `import`. No shell commands or paths come from browser input.

The installed client, menu row, program and catalog belong to the boot-selected
package. USB insertion never replaces them. Across a package update, the running
view reports restart pending and refuses generation-specific edits until restart;
ordinary saved preferences within the same package remain usable. The popup has
its own token, requests, native dialog and lifetime. The two owners arbitrate the
one native modal surface, including suspended progress and pending saves.

`status|settings` is a lightweight saved-state read, also used for USB chooser
metadata. `status|completion` alone requests the full current-boot completion
proof. Default full status reconciles uncertain mutations. Native `status|session`
checks the caller's own close marker; installed-only `status|media` discovers a
runner's final eligible USB offer. These native reads do not execute the shell
backend or take the transaction lock. Every changing command still validates its
revision and physical prerequisites under the writer lock. Maintenance shows
native progress before requesting its change or restart.

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

The dev.9 startup path installs `/usr/bin/open-connect-boot-select` as a trusted
root helper. Its optional snapshot descriptor records the digest, mode and
package; the baseline records absence. An unknown existing path is refused.
The transaction installs the helper before activating its hook. Uninstall
restores the original hook before removing the helper, preserving the explicit
absence check through cleanup. Independent undo uses a compatible dev.9 USB;
unpublished dev.8 downgrade behavior is not supported.

Maintenance fully hashes the OEM, package and composed files, renders both board
profiles, and seals their metadata in `boot.plan` before committing the current
snapshot. The native selector hashes the small snapshot manifest and plan,
checks complete member coverage and metadata, and checks selected executable/UI
bytes while copying them to RAM. It checks firmware identity, physical mounts,
NVRAM, login holds and the actual boot ID. Metadata reuse detects ordinary drift;
it cannot prove uncopied bytes against silent corruption or privileged changes.
Mismatches before debit use the embedded full shell verifier. Lock contention,
duplicate selection and ambiguous durable writes select factory behavior.

Both record flushes precede feature publication. The sole durable record retains
the same attempt budget and ignition rules. A Service Manager one-shot after
`stage_3` verifies and stages the Settings listener independently of USB.
Autostart launches a separately verified RAM ignition observer on both
selected and valid exhausted-budget boots. The installed UI loads its own RAM
assets and attaches locally; opening Settings fetches fresh backend status.
Installed boot-status requests retry within one shared twelve-second deadline
while the listener becomes available.
These implementation checks do not establish startup parity; see the
[matched stock comparison and limits](../docs/stock-startup-comparison.md).

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
