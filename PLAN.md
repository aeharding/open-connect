# Open Connect — working plan

Updated 2026-11-13. Owner: the primary agent, directly.
This is the current roadmap; STEERING.md governs working style. Earlier interim
plans and one-shot handoffs are historical evidence.

## Where we are

- UART, camera, authenticated restart observation and independent file undo work.
- Native disclaimer bypass works on 55.00.750B NA. The paired renderer hook keeps
  intro cleanup until the next screen finishes transitioning. The long blank gap
  was absent in the revised recording; the user still observes a fade out/in.
  Seamless OEM-feeling startup is therefore unfinished.
- Stock native is loaded; the newer single-file Snap JS variant is installed.
  Latest startup: runs/open-connect-snap55/boot-C. It passes access/state checks
  but still shows a brief missing-icon frame. See notes/disclaimer-snap-result.md.
  Exact changing state and recovery bindings: notes/afk-session-status.txt.
- Both-file undo and restored-stock startup were demonstrated in the preceding
  trial. Firmware downgrade and recovery from an interrupted flash are different,
  unproven capabilities.
- Hardware last reported in shipping: USB hub/Ethernet and ACC relay. Do useful
  software work now; distinguish actual hardware requirements from convenience.

## Current: simplest smooth startup

Comparison completed; both approaches still showed a visual handoff. A single-file
variant now uses Mazda Snap only for Disclaimer-to-Home and delays logo disposal
until transition completion. The remaining question is live menu first-paint/icon
readiness; avoid timer tuning or native complexity without evidence.

The user clarified the intended project:
https://github.com/piotrmocko/mzd-v74-tweaks
Inspected commit 5a17963a8631b3b68b9187b6ebbefeef1def05ef. Its
no-more-disclaimer.sh replaces the exact v74 systemApp.js. The actual feature
replaces Disclaimer's Dialog3Tmplt with NoCtrlTmplt, transparent background and
visible Mazda intro surfaces; ready sends DisposeIntroVideo, Global.Yes and
NotifyDisclaimerEnd. It retains the native Disclaimer context and accepts it
immediately. This is the comparison target, not TouchTune or ScreenTune.

Compare actual startup/loading indicator/fades, with our native+JS pair restored
first so the two approaches do not interact. Its unmodified installer requires
74.00.324. A v55 adaptation is possible to investigate: NoCtrlTmplt and the same
logo properties exist in our OEM55 source, but NotifyDisclaimerEnd was not found
as a literal in the captured native55 system library. That absence alone is not
proof of dispatch behavior. Do not copy its whole v74 system app onto v55.
The user explicitly chose the v55 adaptation. It omits the v74-only
NotifyDisclaimerEnd notification and otherwise retains upstream template/properties
and ready-event order. Host checks and the live adapted-mod startup passed;
that initial comparison has since been replaced by the Snap variant. See notes/existing-disclaimer-v55-result.txt. The sampled video still
contains a brief dark transition; do not declare either approach superior.
The prior native+JS demo pair has been independently undone, stock boot verified,
and hardlink holds cleaned before installing this standalone JS comparison.

Save the source diff and original provenance separately from our independent
implementation. Snapshot: runs/mzd-v74-tweaks-comparison. Its CC BY-NC-SA 4.0
license is recorded; comparison code must retain attribution and remain distinct
from any proposed Open Connect redistribution.

## Scope now: upgrade the bench to the latest applicable Mazda firmware

User direction replaces the earlier “v73 later” placeholder. Target the newest
officially applicable release for this first-generation North American CMU.
An exact version is not yet selected. 74.00.324(A) is a documented candidate, not
a verified claim of latest as of today. A newer number for another CMU generation
or region is not a suitable upgrade.

Produce one concrete upgrade recipe:
1. Resolve exact CMU hardware applicability, current Mazda release/package and
   North American variant; obtain the applicable installation instructions and
   package provenance/checksums.
2. Establish the supported sequence from 55.00.750B, including any intermediate
   release and separate failsafe/reinstall order. Do not assume a direct jump.
3. Determine changes to UART/root/SSH and USB execution, and how we retain or
   regain development access. Version-55 offsets and payloads cannot be replayed.
4. Identify usable update USB/hub and bench power/ACC procedure. Establish which
   steps need arriving hardware; Ethernet and the relay are not automatically
   prerequisites merely because they are planned.
5. Preserve device-specific configuration and useful originals off the CMU,
   restore our modifications, boot stock, and establish the actual recovery
   options. A file undo is not firmware rollback; do not promise a downgrade.
6. Run the applicable update procedure when that recipe and its physical inputs
   are available. Verify firmware/region, normal startup, development access,
   USB/hub behavior and an untouched new-firmware baseline before porting mods.

Scoping and preparation are active now. This plan update does not start a flash.
The deliverable is a short executable procedure with concrete remaining inputs,
not a new installer framework or an endless completeness audit.

## Then

- Compare our bypass and the selected existing mod on their supported firmware.
  Keep firmware changes separate from feature effects.
- Port the best OEM-lifecycle fix to the selected modern firmware using its actual
  binaries and source. Test startup, resume/focus paths and full undo.
- User is independently arranging Ethernet/SSH when hardware arrives. Continue
  local firmware analysis now; retain UART for boot/recovery observation.
- Add controlled ACC cycles when available, then measure cold startup and wireless
  CarPlay failures against a stock baseline. RAM pressure remains a hypothesis.
- Turn the proven feature into optional USB install/update/reconfigure/uninstall.
  Publish code and concise reverse-engineering notes with firmware scope.

## Current source leads (checked 2026-11-13)

- Mazda bulletin, November 2022: 74.00.324 or later for its listed models; directs
  technicians to MGSS for update instructions/current releases. It does not prove
  today's latest version or the precise upgrade sequence for this bench:
  https://static.nhtsa.gov/odi/tsbs/2022/MC-10226834-0001.pdf
- ScreenTune currently specifies 74.00.324(A) and explicitly excludes 74.00.331.
  These are vendor compatibility statements, not Mazda release applicability or
  requirements for piotrmocko's separately inspected disclaimer project:
  https://miatafy.com/screentune/troubleshooting/unsupported-firmware/
- Public Miatafy repositories:
  https://github.com/Miatafy
- Earlier retrofit-hub evidence and unresolved preservation details:
  notes/firmware-readiness.txt (dated historical checklist).

Silent Entertainment testing is now unblocked without buying a TAU: the existing
audio-manager enable API opens FM Now Playing and the source list; matching
disable/readback passed. Use an explicit transient bench override, not a firmware
patch. No speakers needed. Playback/cold-start/resume remain untested.
See experiments/tau-bypass/README.md. Current state is disabled again, Home/rootRO.

## Bench profile and GitHub development

Implement the reviewed silent-audio helper and then establish its persistent
startup attachment: [bench/PLAN.md](bench/PLAN.md), [review](bench/REVIEW.md).
Keep bench overrides separate from product features and declared in every test.

Development home: https://github.com/aeharding/open-connect (public).
Original code: AGPL-3.0-or-later. See CONTRIBUTING.md and THIRD_PARTY.md.
Issues track concrete outcomes; PRs carry coherent code, tests and results.

Active GitHub issues:
- Bench profile: https://github.com/aeharding/open-connect/issues/1
- Firmware upgrade: https://github.com/aeharding/open-connect/issues/2
- Startup handoff: https://github.com/aeharding/open-connect/issues/3
