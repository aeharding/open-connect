# Maintenance loading view — dev.17

Dev.17 uses Mazda’s animated, buttonless loading dialog for installation,
updates, reinstalls and removal. It appears before the change is sent, covers
the screen through restart, and uses the stock indeterminate meter. Settings
removal asks only to keep the car on; USB maintenance also asks to keep the drive
connected. [Quick start](usb-installer.md) and [Uninstall](uninstall.md) show the
owner flow.

The exact reviewed source is
[533142d6](https://github.com/aeharding/open-connect/tree/533142d67e7a7e79e34abc6bcb87b7b1f5663f73),
from [CI 45390881869](https://github.com/aeharding/open-connect/actions/runs/45390881869).
The tested ZIP SHA256 is
`503445414eaa5dbe8d646d58afa75fa9770d447c4fa519ac4517b5c9cacd3c1a`;
its public manifest is
`56b036f3ed7526706043e75e4b8e7f6854b12f94288c3d97693ea3874d60db80`.
All 46 public payload hashes and 30 directly corresponding authored files matched.
The four normal-boot comparisons below used that initial revision; they have not
been relabeled as measurements of the later correction.

## What the bench checks establish

On **74.00.324A NA / cmu150_NA**, native 800×480 captures showed the fresh Install
chooser, the full-screen loading view, verified post-reboot Completion and
Open settings. The full Base-enable explanation fits without truncation.
Two timestamped native frames showed different stock-meter pixels, confirming
animation. DOM checks found no progress buttons and an 800×480 shield at top=0.
A software click and Back attempt left the active context unchanged.

Actual Settings removal showed **Removing Open Connect → Restarting Mazda
Connect**, with **Do not turn off the car.** and no USB wording, then reached a
fresh stock boot with installed state removed. An observation-only wrapper delayed
its one restart request by four seconds to retain the restart screenshot;
normal timing runs use no such wrapper. Native screenshot loops and lifecycle
camera captures are excluded from passive boot measurements.

The Update chooser correctly showed dev.16→dev.17; same-version maintenance
showed Reinstall with dev.17 in both version fields. A real reinstall committed
and reached a new kernel. A later uncommanded second reboot and its brief SSH loss
are retained separately; their cause was not established. Camera coverage is not
whole-session reliability evidence.

The initial candidate also exposed a Base-on boot race: automatic completion was
absent despite matching boot metadata and a fresh backend `completionReady=true`.
Reopening the actual maintenance entry showed verified Completion, and Done
worked. The final correction is
[ad10c3a](https://github.com/aeharding/open-connect/tree/ad10c3a68084c7d825c8f536c4414d710e908164),
[CI 45405103481](https://github.com/aeharding/open-connect/actions/runs/45405103481):
only the automatic installed-notice proof window changes from twelve to
**35 seconds**, starting after the browser is shown. Settings reads and mutation/
restart reconciliation keep their previous budgets. Runtime remains **16,377 B /
four pages**. New mock-clock tests accept a late valid proof, bound retries to one
shared deadline, and fail against the original source.

On the exact corrected CI bundle, one Base-on new-kernel boot showed automatic
Completion before any USB reopen or independent backend status check. The native
PNG and empty-action DOM probe captured Done/Open settings, matching boot-page
metadata and no USB loader entry. Subsequent read-only checks verified the exact
installed/runtime SHA, Base=1/Wireless=0 and `completionReady=true`. Done dismissed
the notice, and the same kernel was still present at 145 s. This is one affected
path check, not a new timing cohort or a reliability guarantee.

The corrected ZIP SHA256 is
`f444bbbe895e0b9a8c951e5714a4691d216328053859b10afe53fb4f9b0edffc`;
its public manifest is
`9794c7989454f9ece39a96ad05c80e6c4f653c551c16f93d202638599c40d103`.
All 46 payloads and the corresponding authored files matched. Other UI/transaction/
boot-selection behavior was unchanged by this one-line deadline correction.

Eleven additional native layouts were exercised without backend writes: unknown
installed version, USB Removing/Applying/Checking, Settings Applying/Checking,
Settings pending-save refusal, and known/unresolved errors for both origins.
These are explicitly **layout previews**, not fabricated recovery/error-operation
passes. All opened in the intended Home or Settings context and fit 800×480.

Host fixtures separately cover pre-armed Home holds, VUI Help/Examples yielding,
legacy-loader exclusion, queued Settings saves, explicit refusals, missing replies,
and completion-proof invalidation. Software-injected input and host fixtures do
not qualify physical commander keys, vehicle reverse/CAN transitions or a real car.

## Independent removal and stock closeout

The final installed build was removed directly through **exact CI dev.16 media**
(source `da45ae8`, public manifest
`ab51278b10c59fe3f5a037419f155a63ca94b6198f3d61252852eb56b4c1f2d6`).
Its actual chooser showed dev.17→dev.16; **Uninstall** was selected without
Install/rebase first. The old RAM endpoint/version and initial `uninstall` POST
were recorded independently. The temporary measurement hook was restored to its
original inode and metadata before the removal restart, with its backup retained
until original startup was verified.

The first stock boot’s SSH daemon failed to bind port 36000 because the address
was in use. UART recorded that exact native error. One full thirty-second ACC
cycle recovered access; no uninstall request was resent. This known stock-port
failure is separate from the earlier uncommanded restart and from installer logic.

Final checks verified original OEM hashes/modes, original MMUI/System/VUI mappings,
stock Service Manager/frontend startup, restored services, read-only physical root,
128 KiB read-ahead and absence of installed state, the root helper, published RAM
runtime and measurement hook/backups. Wi-Fi’s BLM API returned status 0 / mode 0
(Off). The exact legacy SanDisk was authorized, mounted read-only and unchanged;
the same SD stayed present. Its old install prompt was canceled and its closed
RAM session removed. All owned uploads and UART/camera/relay/SSH handles were
closed; supply settings were never changed. A future boot can show that legacy
USB’s prompt again while its unchanged old contents remain inserted.

## Nearby normal boots and RAM

The [attempt ledger](assets/performance/loading-ux/attempts.csv) retains four
complete normal boots, three preflight refusals with zero ACC/UART/camera opens,
and the separate resource-only repeat. The refusals were an unapplied saved
choice, an undismissed install notice and a temporary USB/public-versus-installed
manifest mismatch. No failed or refused entry is promoted into a successful boot.

The comparison holds Allow/Skip, Wireless off, Android Auto/Pandora/SiriusXM on,
DVD off and developer access off. Each Base setting has one settled, unchanged
normal boot per version; installation, completion and preference-apply boots are
excluded. ACC is off thirty seconds with B+ supplied. The same FAT SD and
software-quarantined read-only legacy USB remain present; the iPhone stays on
the Mac. SD maintenance is launched manually and does not establish a new
physical USB-insertion test.

The shared five-file stage_1 observer starts resource collection before SSH.
First samples were at 17.73–19.47 s uptime; CPU/RAM before those samples was not
observed by that collector.
Camera and receive-only UART start before ACC; no injected UI input occurs during
these runs. Camera Home bounds use adjacent frames at about 5 fps, with three
visible icon regions at their final positions sustained over the next two frames.
Color fading is excluded from that geometric milestone. UART/SM native uptime and
camera ACC-command time remain separate clocks. This n=1 screening is not a stock
parity or reliability estimate; [#9](https://github.com/aeharding/open-connect/issues/9)
remains open.

| Base | Version | Home ACC bounds (s) | Native stage_1 START (s) | CPU busy, 20–170 s (%) | Own allocated tmpfs (KiB) | Opera private dirty / PSS (KiB) |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | dev.16 | 25.797–25.998 | 8.438 | 26.48 | 404 | 40,416 / 50,538 |
| 0 | dev.17 | 25.788–25.989 | 8.517 | 41.92 | 404 | 40,468 / 50,589 |
| 1 | dev.16 | 23.989–24.190 | 8.591 | 23.09 | 508 | 40,080 / 50,394 |
| 1 | dev.17 | 23.984–24.185 | 8.518 | 24.22 | 508 | 40,784 / 51,098 |

Every selector join recorded **0.00 s** at hundredth-second resolution;
individual selector spans remain in the derived CSV. Selector span is
`selector_exit − hook_entry`; join wait is `join_returned − join_entered` from
`/tmp/open-connect/startup-times`.

Home midpoint differences were −0.009 s with Base off and −0.005 s with Base on,
well below the camera interval. Own allocated tmpfs changed **0 B** in both
pairs. Listener private/PSS was 76/87 KiB with Base off and 76/88 KiB with Base on;
ignition was 132/154 and 132/155 KiB respectively, identical between versions.
Opera private dirty/PSS rose 52/51 KiB in the Base-off pair and 704/704 KiB in the
Base-on pair. These single snapshots do not establish net-system RAM causation.

The first Base-off candidate had a large late CPU0/system-time outlier:
60–170 s CPU0 busy was 60.87% versus 20.29% in the control. It is retained rather
than replaced by a cleaner attempt. The Base-on CPU difference was +1.14
percentage points in this single pair. No zero-CPU-overhead claim follows.

Allocated tmpfs accounting counts each device/inode once across **all node types**,
including the allocated long System-UIA symlink. Earlier reports counted regular
files only; those absolute totals are not silently relabeled. Helper private pages
and PSS, Opera private/PSS and named system memory fields are recorded separately.
Equal file pages alone do not establish equal total process or system RAM.

## Supplemental CPU and first-use dialog memory

The original CPU outlier remains in the primary table. A later Base-off ACC
apply boot supplied a separately labeled resource trace. Its **clean 20–120 s
prefix** measured 34.751% CPU versus 34.736% in the dev.16 control; the first
dev.17 outlier was 47.514% over that same prefix. In 60–120 s CPU was
14.17% for the dev.16 control, 33.80% for the first dev.17 run and 14.76% for the
supplemental repeat. This did not reproduce a deterministic
version-wide CPU penalty, but it does not establish the first outlier’s cause.
A process probe began at 125.76 s and dialog work at 136.71 s; neither is included
in the supplemental comparison. That repeat has no camera milestone and never
replaces a primary attempt.

One same-process first-use probe separated a static Mazda dialog from style27:

| State (KiB) | Opera private dirty | Opera PSS |
| --- | --- | --- |
| Before either dialog | 40,648 | 50,772 |
| Static dialog visible / after close | 41,968 | 52,100 |
| First style27 visible / ten seconds after close | 42,504 | 52,688 |

The additional style27 activation cost was **536 KiB private dirty / 588 KiB
PSS** after the static control had initialized. This includes its native control,
image and browser cache work; it is not isolated solely to APNG decoding.
A separate three-cycle style27 probe showed PSS 51,106→52,862 KiB on first use,
then the same value after each close and subsequent opening. No additional PSS
was measured across those three cycles. The first-use increase remained at the
last observation; it is not described as freed on close. Accepted maintenance
restarts the CMU, while a refused operation may leave those browser caches until
a later restart. These findings require explicit owner RAM disposition before merge; unchanged
allocated tmpfs is not a waiver for the observed Opera memory cost.

The [dialog-memory samples](assets/performance/loading-ux/dialog-memory.csv)
retain each first-use/cleanup observation and its actual uptime.

The [normal-boot table](assets/performance/loading-ux/normal-boots.csv) retains
all named fields and actual windows/measurement ages. The
[supplemental CPU table](assets/performance/loading-ux/cpu-repeat.csv) keeps both
window definitions and all three attempts. CPU busy is the difference in the
first eight `/proc/stat` counters, excluding idle and I/O wait, divided by their
total difference. Memory columns are named kernel metrics; lower MemFree alone
is not a net-RAM conclusion.

## Reproduction and private evidence

The untouched capture worktree is `b0f1492abe3b157eac3dad105cc41a42b4967681`.
Run its `open_connect.startup_reference` with the verified installed package ID,
`--condition open-connect --base 0` (then `1`) and `--pandora 1`, preserving the
choices and fixture above. Do not pass its older optional wireless guard for this
candidate; verify all four Services and Wireless=0 separately in fresh status.
The observer manifest is
`6d795adc75cb0c16823eebf49f414dc48e4b0c686b3920b795fea7140657e42c`.

Raw captures, exact commands, native screenshots, manifest verification and
per-inode/smaps receipts were retained privately and are not distributed.
Home annotations use `startup_annotate` at
`b111f19b24355568e3be066b153a87785ab12434` with `--camera-only --no-projection`;
no kernel/video clock mapping was collected. No projection timing is inferred.
Only reviewed, unedited owner-guide PNGs and derived tables are published.
