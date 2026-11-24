# Sparse native UI loading — dev.16

The dev.16 candidate avoids loading disabled MMUI and voice modules when Base
optimizations are enabled. It also delays OEM Navigation independently by twenty
seconds after Mazda's stage_3 when Base and Wireless CarPlay are both on.
[Services](services.md) describes the choices.

Three primary starts per version showed **Home about 0.385 s earlier** and
**104 KiB more own allocated tmpfs**. MMUI/voice PSS was lower, but achieved
projection workloads differed: none of four complete dev.15 attempts qualified
as visible Maps; all three dev.16 attempts did. **Comparative Maps speed, CPU
parity and net-system RAM savings are not established.**
[#9](https://github.com/aeharding/open-connect/issues/9) remains open.

## Fixture and every attempt

Both cohorts used Allow/Skip, Base=1, Wireless=1, Android Auto=1, Pandora=1,
SiriusXM=1, DVD=0, UART=0 and SSH=0. Existing owner-key lab SSH is separate from
the product setting. The iPhone stayed USB-connected to the Mac, with Wi-Fi and
Bluetooth on and dark Maps intended as the foreground. ACC was off thirty seconds;
B+ stayed supplied. These are fresh-kernel ACC starts, not overnight cold boots.

The same FAT SD card was present throughout, containing an invalid-license map
copy and the manually launched maintenance bundles. A separate read-only legacy
installer USB remained inserted. Its exact device identity was software
deauthorized by the shared observer after OEM enumeration on every recorded
boot, preventing its old installer from launching. Its bytes were untouched.
This present-SD/quarantined-USB fixture differs from earlier no-SD datasets.

Acquisition was blocked: three primary dev.15 controls, one supplemental control,
upgrade/setup, then three primary dev.16 starts. The **ten-record attempt
ledger** contains five control entries and five candidate entries. It retains:

- One broken-relay acquisition with no new kernel and incomplete capture.
- Two dev.16 pre-hardware tooling refusals: an undismissed install notice and a
  capture guard that only recognized dev.15. Neither transmitted relay commands.
- Seven complete new-kernel captures: **1,212 samples**, including **1,038** in
  the six primary starts. Supplemental control 5 is never promoted into that cohort.

Controls 2, 3 and supplemental 5 had no SessionActiveCP in their captures. Control 4 reached
it but displayed native Home. Thus there were **zero qualified visible-Maps
observations in four complete controls**, versus three in three complete candidate
starts: **0/4 versus 3/3 completed captures**, not ten projection observations.
The two pre-hardware refusals contribute zero projection observations, as does
the no-new-kernel acquisition; all three remain in the attempt ledger. These
complete-capture counts are not whole-ledger reliability rates, and the small
blocked sample does not establish universal reliability.
The excluded setup's successful projection remains excluded. Credential-query
error(-1) appeared in failed controls and successful candidate starts, so that
message alone does not establish the cause of a connection miss.

| Version / capture attempt | Home ACC bounds (s) | Maps ACC bounds (s) | CPU busy (%) | Min MemFree (MiB) |
| --- | --- | --- | --- | --- |
| dev15 / 2 | 25.400–25.601 | Unqualified | 23.63 | 280.66 |
| dev15 / 3 | 24.994–25.195 | Unqualified | 24.16 | 276.18 |
| dev15 / 4 | 25.194–25.395 | Unqualified | 25.69 | 270.34 |
| dev15 / 5 (supplemental) | 26.221–26.422 | Unqualified | 24.02 | 279.04 |
| dev16 / 3 | 24.809–25.010 | 44.585–44.786 | 32.33 | 268.31 |
| dev16 / 4 | 24.793–24.994 | 40.949–41.150 | 31.70 | 270.87 |
| dev16 / 5 | 25.604–25.805 | 42.766–42.967 | 32.57 | 270.66 |

Home median midpoints were **25.2945→24.9098 s**, difference **−0.3848 s**;
differences of median frame endpoints were **−0.5858..−0.1838 s**. These brackets
are camera uncertainty bounds, not confidence intervals. Native Service Manager
stage_1 START medians were **8.472→8.493 s**. Every selector join recorded
**0.00 s** at hundredth-second resolution. UART native-clock values and camera
ACC-clock values are kept separate.

Home requires three visible icon regions to register at their final positions,
mean gradient correlation above 0.95, for three successive frames; this camera
does not qualify all five icons. Maps requires its sidebar plus roads/labels
around the central marker, sustained in the next two frames. Earlier partial
central tiles do not qualify. Neither criterion proves input or audio readiness.

## Named memory observations

Regular-file allocations under `/tmp/open-connect` count each device/inode once,
including hardlinks. They exclude directory/inode slab and transient selector
pages. Primary snapshots were taken at about 234–239 s uptime after capture.

| Own RAM component (KiB; medians) | dev.15 | dev.16 |
| --- | --- | --- |
| Unique allocated tmpfs files | 444 | 548 |
| Listener private / PSS | 72 / 83 | 72 / 83 |
| Ignition private / PSS | 132 / 153 | 132 / 153 |

The 95,537-byte VUI ELF occupied **104 KiB allocated** on this tmpfs. Its same-inode
hold adds no second payload copy. VUI XML, the Nav helper and firmware closure
add 4 KiB each; smaller MMUI XML saves 4 KiB and the reduced session closure
saves 8 KiB, accounting for the **+104 KiB** total. Symlink targets remain stock.
Listener private dirty was 68 KiB and ignition private dirty 132 KiB throughout.
One primary control ignition PSS sample was 152 KiB; the other primary samples
were 153 KiB. The supplemental control was 154 KiB.

| Application PSS (KiB) | dev.15 primary samples | dev.16 samples | Median difference |
| --- | --- | --- | --- |
| MMUI | 13,844 / 13,804 / 13,843 | 12,859 / 12,871 / 12,827 | −984 |
| VUI | 2,691 / 2,691 / 2,690 | 2,597 / 2,597 / 2,593 | −94 |
| Opera | 47,942 / 50,618 / 49,950 | 50,390 / 49,946 / 50,370 | +420 |

The sum of the two per-application PSS medians was **1,078 KiB lower**, an observed component
change under different achieved projection workloads. This is not isolated
net-system memory proof; do not add mapped tmpfs to PSS a second time.

The following columns are separate medians of each run's last sample inside
20–170 s, not one shared physical sample. The workload mismatch applies to
all whole-system CPU, memory and I/O comparisons.

| Last-sample metric (MiB) | dev.15 | dev.16 |
| --- | --- | --- |
| MemFree | 277.984 | 272.629 |
| Cached | 149.770 | 149.648 |
| Shmem | 4.023 | 4.086 |
| AnonPages | 216.957 | 221.707 |
| Slab | 19.930 | 20.047 |
| Buffers | 5.957 | 5.984 |

CPU busy was **23.63/24.16/25.69%** versus **32.33/31.70/32.57%** in 20–170 s.
All candidate starts displayed Maps while none of the controls did; this is
neither a qualified CPU gain nor an attributable regression. Cached, Shmem,
AnonPages and Slab remain separate from MemFree.

Whole-device read-volume medians in that window were **53.570→55.566 MiB**
on ffx01 and **31.374→31.397 MiB** on mmcblk0. These are descriptive
workload observations, not isolated sparse-loader effects or complete-boot I/O.
Partition rows overlap their whole devices and must not be added.

## Native loading and Navigation

The selected MMUI XML keeps retained application IDs unchanged. Base-off uses
stock VUI and all 43 MMUI definitions. With Base on, only disabled groups are
omitted. The VUI service has a SHA-guarded 24-byte pathname replacement in a
private RAM copy; code, ELF headers and length are unchanged. Its XML and
retained plugin symlinks survive persistent-state purge until restart.

The independent Nav gate has no CarPlay/NMS parent. It waits twenty seconds
after stock stage_3; SM can also release it on the configured 22-second timeout.
Existing Nav prerequisites and NNG demand-start remain. Primary jcinavi START
medians were **21.132→41.104 s**, and STARTED **24.411→42.297 s**. This measures
service readiness only: the invalid-license SD and non-tuner bench do not
qualify guidance, voice recognition, audio, CAN, reverse or real-car behavior.

## Functional screens and maintenance boundary

With Base/Wireless on and all four Services off, the actual selection had
**33 MMUI definitions and 36 VUI plugin files**, with no forbidden module mappings.
The native Audio Sources list retained FM, AM, Bluetooth, CarPlay, USB 1/2 and
AUX without disabled-source ghost rows. Replayed native AA visibility messages
through both the OEM handler and its already-bound callback kept AA hidden and
preserved USB_A at master index 12. These are software interaction checks, not
Android-phone or physical-input qualification.

The real persisted FM 102.9 favorite was selected through Mazda's existing
handler and left a responsive Favorites page. Fuel Consumption opened, and
Applications, Audio Sources and Open Connect Settings remained reachable.
The non-tuner bench has eight FM favorites and no SAT/XMAD favorite. Unavailable
satellite-favorite behavior and radio playback therefore remain unqualified;
no fake favorite or GUI-only substitute was created.

Fresh Base-off/Wireless-off starts with AA on and off used stock VUI, all 43
MMUI definitions, 128 KiB read-ahead, no Wave C assets/aliases and no Nav gate.
Both had **400 KiB allocated own files**, versus the earlier dev.15 Base-off
reference's 404 KiB. This is file-allocation accounting, not total-RAM or matched
Base-off timing proof.

A separate same-choice Base/Wireless-on, AA-off/Pandora-on/SiriusXM-on/DVD-off
reference with disclaimer bypass off measured **400→552 KiB**, **+152 KiB**.
Ages/foregrounds are retained in the separate functional table and are not
pooled with the primary timing cohort. Max-off's candidate page occupied two
4 KiB blocks, versus one in the primary preset; its own allocation was 552 KiB.

The separate max-off pair held the same Base/Wireless/Services choices and
native Audio Sources foreground. Probe starts were **240.73 s** (dev.15) and
**242.90 s** (dev.16). Actual MMUI/VUI smaps sampling began at
**242.93/243.17 s** and **246.20/246.41 s**, respectively. MMUI PSS was **13,940→11,695 KiB**, VUI **2,698→2,459 KiB**:
**2,484 KiB (about 2.43 MiB) lower combined PSS**, while own allocated files
rose **444→552 KiB (+108 KiB)**. This is one functional pair at the stated ages,
not a timing cohort, repeated effect estimate or isolated total-RAM saving.
The other functional rows have different ages and must not be pooled with it.
In particular the warning-off candidate's 66 s PSS is still an early observation;
its allocation check does not establish settled application memory.

Exact dev.15 media's real Install/update rebased the running dev.16 installation
from preserved stock originals, retaining choices and the stock-five baseline.
There is no version-based dev.15 downgrade refusal. Its actual Uninstall button
then removed the rebased dev.15 durable state while dev.16's native modules were
still loaded and a bounded test interceptor held automatic restart transmissions.
With bypass off, the RAM VUI ELF/hold, XML and 44 retained plugin files freshly
reopened after purge, and the stock System UIA reopened. This first sequence
proved lifetime across rebase/removal, not direct removal of installed dev.16.
No second VUI payload copy or persistent outside hold was needed.

A separate direct warning-off check installed the exact dev.16 CI bundle from
stock, then booted **Base=1, warning=0, Wireless=0, AA/Pandora/SiriusXM=1, DVD=0**.
The voice service was RUNNING with the selected RAM ELF, same-inode hold and
46 plugin paths; System retained its stock library pathname. Old dev.15 media
showed **From: 0.3.0-dev.16 / To: 0.3.0-dev.15**. The old-media request trace from that choice onward was
**Uninstall, Restart**, with no Install/update, Set or recover request: Uninstall
used dev.16's current revision directly, without rebasing first.

After purge, both VUI ELF paths reopened with the exact candidate SHA, XML and
all **46 plugin files** reopened, and the stock System library reopened with its
original SHA. Native Home and the MMUI WebSocket remained alive. One automatic
restart was held for those checks, then one explicit request to the verified
old-media RAM backend requested the restart. The following stock boot passed
the complete restoration check, retained Wi-Fi Off and reauthorized the unchanged
SanDisk read only; its legacy chooser was canceled and its closed RAM removed.
All handles closed. This additional functional check used
no timing observer and did not add projection/resource observations to the
measurement ledger. A setup backend call had refused `session_replaced` before
any Set; unchanged state was checked and the verified dev.16 RAM service restored
before making the two intended settings changes.

**Fresh-page reload remains limited.** In that held interval a new browser
context loaded OEM systemApp.js and connected its MMUI WebSocket but remained
in IntroAnimation at seven seconds. UART later recorded GUI Manager missing ten
seconds of heartbeat, closing Opera at native 355.54 s; SM then triggered its
watchdog reboot. The explicit restart helper refused before transmission, so
no duplicate restart was sent. The following stock boot passed original hashes,
modes, loaded routes, restored services and read-ahead checks; the measurement
hook was deliberately retained for the remaining checks. This reproduces the
previously retained reload boundary, not a qualified usable mid-uninstall reload
or proof of an underlying JavaScript cause.

With bypass on, the inherited dev.15 System UIA pathname may become dangling
through purge while its existing native mapping remains alive until restart.
The real warning-on old-media Uninstall passed too: all 36 retained VUI plugin
files reopened; the first **16 ELF identification bytes** of the mapped System
module were independently read through /proc/PID/mem and matched the original's
first 16 bytes. This did not compare the complete ELF header or module. Its
fresh browser context again loaded OEM System and connected MMUI while remaining in IntroAnimation at seven
seconds. UART also recorded GUI Manager closing Opera at **583.814 s** and SM
stopping watchdog pings at **584.969 s**, before the verified old-media backend
acknowledged the explicit restart request. Both the watchdog path and explicit
request were present; which mechanism caused the next reboot remains open.
One automatic restart transmission had been intercepted. Fresh native pathname
opens and browser contexts are separate checks; no fully usable reload is claimed. The RAM VUI
paths do not inherit the persistent System-path dependency.

Removal returned to original OEM hashes/modes, original UIA/MMUI/VUI mappings
and stock SM/Opera routes, restored services, saved access policy and the
originally absent touchscreen NVRAM key. Physical root stayed read only and
read-ahead returned to 128 KiB. The observer's independent restore put back the
original stage_1 inode; an original-script startup passed before its nine owned
files were removed. Native Wi-Fi was set Off through its discovered wlan0 API
and retained Off after a full thirty-second ACC shutdown/start.

Removing quarantine let Mazda reauthorize the same SanDisk drive and mount it
read only; its legacy installer manifest was unchanged. Its automatic dev.1
chooser was canceled without installation, its client disposed and only its
verified closed RAM session removed. That unchanged installer can show its
normal chooser again after a later boot. The final stock check left no Open Connect
state, helper, runtime, measurement hook or extra mounts. SD content was kept;
UART, camera, relay, supply and SSH handles were closed.

The longer Base-enable message was visibly truncated in Mazda's dialog.
[Issue #132](https://github.com/aeharding/open-connect/issues/132) tracks the
shorter copy and a new guide capture; the clipped image is not published.
The qualified runtime remains byte-identical to da45ae8.

The owner explicitly authorized overnight merge at **2026-11-23T23:48** only
with Astra approval, green CI and no performance or functional regressions,
subject to **≤+152 KiB own allocated tmpfs with Base on** and **≤0 B with Base
off**. That authorization covers the measured **+104/+108/+152 KiB Base-on**
and **−4 KiB Base-off** configurations, as recorded in the
[steering agreement](https://github.com/aeharding/open-connect/blob/main/STEERING.md).
It is not a general RAM waiver or a claim of matched CPU/net-system RAM or stock
parity; #9 remains open.

## Builds and reproduction

Control: exact **0.3.0-dev.15**, source
[7e81225](https://github.com/aeharding/open-connect/tree/7e8122571d241fc3b58d0356687f0932bdacd5d0),
[CI 45207857419](https://github.com/aeharding/open-connect/actions/runs/45207857419).
Candidate: exact **0.3.0-dev.16**, source
[da45ae8](https://github.com/aeharding/open-connect/tree/da45ae8bcc556474b9949025011907e04c63695c),
[CI 45336747490](https://github.com/aeharding/open-connect/actions/runs/45336747490).
Candidate ZIP SHA256:
`9d3b9f14d1602c53a6e0958873ba6696a4d26ae53e4e780a7e75ee79b6f5df69`.
All 46 public payload members and 35 authored inputs matched; private INSTANCE
binding is separate. The source review covers this exact runtime revision.

Controls used
[`9fcba19`](https://github.com/aeharding/open-connect/tree/9fcba1971b22a48c23d899475a2f1d7b8dd98301);
the three accepted candidate captures used
[`b0f1492`](https://github.com/aeharding/open-connect/tree/b0f1492abe3b157eac3dad105cc41a42b4967681).
The latter only recognizes dev.16's unchanged Services choices in the host
guard; target observer bytes are identical. Both wait finitely for the identified
removable USB before software quarantine. The five-member target
observer manifest is
`6d795adc75cb0c16823eebf49f414dc48e4b0c686b3920b795fea7140657e42c`.
Quarantine must be explicitly bound to the operator's own device identity;
do not apply this bench's policy to an unidentified drive.

Start UART and camera before ACC. The local resource sampler runs 180 s with a
190 s watchdog; video continues 210 s and retrieval starts at 225 s. It never
waits for SSH to begin logging. Here USB-enumeration waiting delayed first
resource samples to **17.80–18.17 s** uptime; earlier resource use is unobserved.
Use the existing [startup clock procedure](startup-comparison.md#source-pins-and-reproduction):

~~~sh
python -m open_connect.startup_reference --live --host my-cmu \
  --ssh-config /path/to/trusted-ssh-config --condition open-connect \
  --package INSTALLED_PRIVATE_PACKAGE_DIGEST --base 1 --wireless 1 --pandora 1 \
  --bundle runs/my-cohort/trial-1 --label 'dev16 B1 W1 AA1 P1 SXM1 DVD0 dark Maps'
~~~

Keep the capture checkout on PYTHONPATH and set OC_WORKSPACE to it. After all
capture handles close, take same-boot clock exchanges plus Services/selector and
RAM postflight. The retained analysis checkout [916e6e4](https://github.com/aeharding/open-connect/tree/916e6e49172449702918679c8a5d8fd349028516) provides the
parameterized probes and exporter. Actual collection used the same appended
per-process smaps commands in a private guarded probe; the public optional
`--app-pss` flag is their reproducible packaging, not a claim that old captures
used a newer script.

~~~sh
python -m open_connect.clock_reference --live --host my-cmu \
  --ssh-config /path/to/trusted-ssh-config --expect-boot BOOT_ID \
  --bundle runs/my-cohort/clock-1
ssh my-cmu 'timeout -t 50 sh -s -- BOOT_ID 1 PRIVATE_PACKAGE_DIGEST' \
  < cmu/bench/wave-b-services-postflight.sh > runs/my-cohort/extra-1.out
ssh my-cmu 'timeout -t 60 sh -s -- BOOT_ID PRIVATE_PACKAGE_DIGEST --app-pss' \
  < cmu/bench/wave-b-ram-postflight.sh > runs/my-cohort/ram-1.out
python -m open_connect.startup_wave_c PRIVATE_CAPTURE_ROOT OUTPUT_CSV_DIR
~~~

Select resource endpoints inside 20–170 s; CPU busy excludes idle and iowait.
Disk counters use 512-byte sectors; partitions overlap the whole device and must
not be added to it. Home review uses the existing geometric registration helper;
Maps uses adjacent reviewed PTS with `startup_annotate --projection maps`.
No-projection controls use `--no-projection`. The exporter reparses saved traces,
reproduces memory.csv, validates clock/frame arithmetic and retains the declared
attempt labels. Capture checked the transmitted trace digest; export validates
saved data. Raw capture manifests are unchanged. Discard native event times if
either Linux-banner or boot-marker count differs from one.

Downloads: [attempts](assets/performance/sparse-native-loading/attempts.csv),
[timings](assets/performance/sparse-native-loading/timings.csv),
[resource summaries](assets/performance/sparse-native-loading/summary.csv),
[all samples](assets/performance/sparse-native-loading/samples.csv),
[storage](assets/performance/sparse-native-loading/io.csv),
[own RAM](assets/performance/sparse-native-loading/own-ram.csv),
[application PSS](assets/performance/sparse-native-loading/app-pss.csv),
[selector phases](assets/performance/sparse-native-loading/selector-phases.csv),
[native services](assets/performance/sparse-native-loading/native-services.csv),
[native wireless events](assets/performance/sparse-native-loading/native-wireless.csv)
and [separate functional RAM](assets/performance/sparse-native-loading/functional-ram.csv).
Raw captures, OEM files, device identifiers, credentials and personal maps stay private.
