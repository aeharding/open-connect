# Guide media provenance

## Touchscreen PR #205 captures 2026-11-26

`setting-touchscreen.png` and `touchscreen-choices.png` are direct, **unedited native 800×480 `/dev/fb0` BGRA readbacks** captured during live v74 bench qualification of GREEN CI PR #205 (`ba4e6ee6`, [CI 45881169287](https://github.com/aeharding/open-connect/actions/runs/45881169287), merged `8094911b`, artifact `15147692204`). `setting-touchscreen.png` supersedes `setting-touchscreen-while-driving.png` on the welcome and Settings pages; `touchscreen-choices.png` shows the three-choice `Touchscreen` radio submenu (`Factory behavior`, `Always enabled`, `Always disabled`).

Navigation used Commander Dial events (`Virtual Keyboard` → `filtered-keyboard0`) only, with touch disabled (`touch=2`) on `74.00.324A NA/cmu150_NA`. Both full PNGs were visually reviewed for zero PII, VIN/serials, phone names, credentials or diagnostic overlays. Physical Commander hardware and real-car use remain unqualified.

| Asset | SHA-256 |
| --- | --- |
| `setting-touchscreen.png` | `747f9c6123c3071d445a936f20f368d90ff4d0f32e72508c94d9f9684faf8f29` |
| `touchscreen-choices.png` | `31212b0fa8024a21d3b374cfe214825da5c2a47964dc0587fdba25c9ad0f65e2` |

Private originals: `runs/separate-installer-settings-20261125/touch87-ci-bench-20261126/boot2-oc-back-enabled.png` and `boot2-touchscreen-submenu.png`.

## Audio sources PR #149 captures 2026-11-25

`setting-pandora.png` and `setting-siriusxm.png` replace the earlier dev.19
captures with direct, **unedited native 800×480** Commander-highlighted PNGs
from the **post-dev.20 PR #149 candidate**, source
`ecddb381185ec4985b87b5ab6acbb3792807fe21`,
[CI 45597702470](https://github.com/aeharding/open-connect/actions/runs/45597702470),
merged as `291492fa4badba2d8479f23add82867d83bf68b6` (`291492fa`).
VERSION still reads dev.20; these are **not captures of the published dev.20
release**. They match merged main's Audio sources menu: **Pandora and SiriusXM
only, no DVD row**, both on. **Bluetooth was OFF** during capture.

The capture operator and documentation implementer visually reviewed each full
image: **zero visible PII**, VIN/unit serials, credentials or diagnostic overlays.
Native red focus comes from Commander navigation, with no image edits. The
implementer inspected and hash-checked the supplied originals offline; this
change performs no live hardware verification. Real-car audio remains unqualified.

| Asset | SHA-256 |
| --- | --- |
| `setting-pandora.png` | `90f9c522c97a251e3c0796dcc8ffb0489a25c95bc3f0b8f285aaf70e707f0670` |
| `setting-siriusxm.png` | `adc2e570d4e47c85bd64d22c130987f66958629309061e5a41da0458fc3a2944` |

Private supplied originals:
`runs/acc-bench-20261125/audio-sources-pr149-pandora.png` and
`runs/acc-bench-20261125/audio-sources-pr149-siriusxm.png`.
`PR149-QUAL.md` and `pr149-screenshots.json` retain capture/qualification receipts.
The PR #149 packet covers normal same-version Reinstall, DVD policy in both Base
states, migration and Settings Uninstall; it has **no new performance cohort**.
Published-dev.20 performance results retain their separate source identity.
Only these two reviewed PNGs are copied; raw captures remain private.

## Commander Dial MP4 walkthroughs and Apply changes 2026-11-25

The five `walkthroughs/*.mp4` videos and three Apply changes PNGs show
**0.3.0-dev.20** on **74.00.324A NA/cmu150_NA**, captured from reviewed source
[`e29b58258c0c9e9f4c4689c7912f634b80008424`](https://github.com/aeharding/open-connect/tree/e29b58258c0c9e9f4c4689c7912f634b80008424),
[CI 45578042314](https://github.com/aeharding/open-connect/actions/runs/45578042314).
This is their exact capture candidate, not the later final dev.20 qualification
build. Older captures below retain their own identities.

The operator visually reviewed all five final videos and three full PNGs for
personal information, credentials, diagnostic overlays and framebuffer tearing.
Navigation used Mazda Commander Dial events (rotate, select and right), with no
touch input. Bluetooth was **off during the five MP4 walkthroughs**. The three
Apply changes PNGs were captured at **03:06–03:08 CST**, before Bluetooth was
turned off at **03:16 CST** for the video pass. All three PNGs were reviewed and
show no visible personal identifiers. No VIN, unit serial, phone identity or
personal map appears in the reviewed media. These are bench software UI captures,
separate from physical Commander hardware and real-car qualification. The documentation implementer
inspected the three PNGs and verified all eight copied files offline.

Each video starts at **Home**, follows Mazda’s native menus and retains real-time
playback without acceleration. They are **800×480, 10 fps, H.264/yuv420p**, with
no audio. H.264 is lossy; RGB pixel identity with the framebuffer is not claimed.
Torn framebuffer samples were rejected and the **previous intact native frame
was held at the original timestamp**. No UI pixels were invented and no waits
were cut. Occasional capture stutter remains. These are **walkthroughs only, not
performance timing evidence**.

| Video | Duration | Bytes | Held frames / total |
| --- | ---: | ---: | ---: |
| `walkthroughs/open-connect.mp4` | 9.4 s | 132,589 | 7 / 94 |
| `walkthroughs/carplay-android-auto.mp4` | 11.0 s | 141,895 | 12 / 110 |
| `walkthroughs/audio-sources.mp4` | 11.1 s | 125,771 | 15 / 111 |
| `walkthroughs/developer-options.mp4` | 11.4 s | 134,300 | 15 / 114 |
| `walkthroughs/version-info.mp4` | 10.4 s | 126,677 | 8 / 104 |

The PNGs are unedited native **800×480** readbacks. The disabled capture focuses
adjacent **Uninstall** because Mazda’s Commander skips disabled rows; Apply changes
remains visibly grey. The enabled and confirmation captures show a genuinely
saved change waiting for restart, not a simulated state.

| Asset | SHA-256 |
| --- | --- |
| `walkthroughs/audio-sources.mp4` | `79a0a92e87bd45e7bfe82b9850bf7703890fc145bf1b5ea60f2ec6953f4cecb1` |
| `walkthroughs/carplay-android-auto.mp4` | `5f5541526ac1724fb8655f574e73b62e97e0d7c6803f3472336cd4c95c28920c` |
| `walkthroughs/developer-options.mp4` | `80a6cb3de500d810bdd29ea57b86e0fb6a5528e85a7a52b42082142b4efb740b` |
| `walkthroughs/open-connect.mp4` | `d372dbcf703996721b93a7ef96af75e8ff85721d4cbb194bd6d2e8a8f89c0538` |
| `walkthroughs/version-info.mp4` | `23ff6a954f496c3eca4151ecb06a71589b19adc83476becd9af979221b21ccdf` |
| `apply-changes-confirm.png` | `41302b32a058b15fda7ff8af217d48f2657a976ba0bc5f0fc66cab0d92c554a7` |
| `setting-apply-changes-disabled.png` | `7f675da6a1b387a9b4cc12d60582a12f22a9ba54ad02e21a3a48b0935db80202` |
| `setting-apply-changes-enabled.png` | `5ac5a1d2a406f9427de9374f101ef13fac00340a66009e3557343bc99f94b131` |

Private supplied originals: `runs/dev20-qual-20261125/videos/{name}.mp4`,
`apply-changes-disabled.png`, `apply-changes-enabled.png` and
`apply-changes-confirmation.png`. The operator’s `videos/manifest.json`,
`videos/SHA256SUMS`, `videos/frame-rejections.json` and `FINAL-QUAL.md` identify
the source, exact file bytes, rejected sample indices and qualification limits.
Raw masters and capture collections remain private; only the reviewed guide
media listed above are included.

<span id="commander-dial-setting-captures-november-24-2026"></span>
<span id="commander-dial-setting-captures--november-24-2026"></span>

## Commander Dial setting captures 2026-11-24

The fourteen original November 24 `setting-*.png` images were direct, unedited native **800×480**
**BGRA framebuffer (`/dev/fb0`) readbacks**, supplied by the capture operator.
They showed **0.3.0-dev.19** on **74.00.324A NA/cmu150_NA**. The two
Audio sources row captures are superseded by the PR #149 images above; their
original hashes below are historical, with old bytes retained in Git. Navigation used
Commander Dial events, with no touch injection; Bluetooth was disconnected.
Each complete PNG was visually reviewed by the documentation implementer and
coordinator for personal data, credentials, clipping and diagnostic overlays.
The red highlight is Mazda’s native row focus, not an image edit.
These are bench software UI captures, separate from real-car qualification and
physical Commander Dial hardware validation.

The coordinator identified **v0.3.0-dev.19**, tag commit
[`f478f3b2`](https://github.com/aeharding/open-connect/tree/f478f3b282f6987d86e04c03d83b1a6971d5a3db),
with two distinct archive identities:

- Published GitHub [v0.3.0-dev.19 prerelease](https://github.com/aeharding/open-connect/releases/tag/v0.3.0-dev.19)
  ZIP, as recorded in the release’s `SHA256SUMS`: `c2c09b3123a2145f3582d3ee7f1e692581b1196ab18c5ba60fc198d79716c486`.
- Local coordinator build ZIP: `d4f0feaf4813ef5707d0f2528a0a98b70b571b1def56582b50e35ec463e5048d`.

The coordinator reports that all **50 extracted file members are byte-for-byte
identical** between these archives; the ZIP archive hashes differ.

The documentation implementer inspected and copied the supplied files offline;
no new live identity or package verification was performed for this docs change.

Captures show Touchscreen Allow, disclaimer Skip, Startup optimizations and
Wireless CarPlay on, Show CarPlay on connection Factory, Android Auto/Pandora/
SiriusXM on and DVD off. A highlighted row is not a changed preference; shown
values are not all fresh-install defaults. The Developer options capture shows
its parent row rather than its access controls.

| Original November 24 asset (Pandora/SiriusXM superseded) | Original SHA-256 |
| --- | --- |
| `setting-touchscreen-while-driving.png` | `cfd64b084b0417cd531957390e6875c2f5e5df17b58cae044a9cca80f769a3aa` |
| `setting-startup-disclaimer.png` | `9b5eaf8fadc9af939db645fb126070c30e112b0424ebbbb276a0d9a2cbad19ed` |
| `setting-startup-optimizations.png` | `4750d5d7841f1c17329fc6820335f6ba4f37f54dd2259fc6b1589ee3ad3cb7a0` |
| `setting-carplay-android-auto.png` | `6c11b8bf9c8f51f61b95bef93b5bf5110a3e1581f2b4a3a592d3f7fcd815e0d3` |
| `setting-wireless-carplay.png` | `d61310e8fb7f10e6dad0616a01188f6165977e5132d3b810f3d321e46cb4cc03` |
| `setting-show-carplay-on-connection.png` | `33eebd70ca15e1d0caa1826ec40c339372e87c9640edb552a90c4cf36073e652` |
| `setting-android-auto.png` | `342879f73ca3974a1ee0694d64f40ddba41410d0bcecab10be675f8398031b2e` |
| `setting-audio-sources.png` | `15a577980a3d1553bb1d140e9894e2b63171e00bb40646c2d2f3af594dd1c725` |
| `setting-dvd.png` | `61f6f0234040b201af85db8f1df4ccbbf847f84e00918f6017b546ca39419c16` |
| `setting-pandora.png` | `f8a8a82173921c6b8aa843630d6a5f0a59e80b0333312ebaeaff646b0197ec10` |
| `setting-siriusxm.png` | `910c54500e9e8507ba857108515d62d7968ab83a8c4f163e1fdf158b305c3555` |
| `setting-developer-options.png` | `384aca291b48f190823f346433fc04257752798828ad61fef89fe320c84c76ce` |
| `setting-uninstall.png` | `f7e12d35c2b77027a19609d4b6237e83ba9c4079e9a486d45cf4477f32321649` |
| `setting-about.png` | `a26b812d028c3fdecdfb224a06e187cf88f05e2d72a9544a6e81b03916d73b9d` |

Private supplied originals: `runs/fb0-capture-proto/highlighted/{name}.png`;
`events.json` in that directory records the initial twelve captures. The final
Touchscreen While Driving and Startup disclaimer PNGs were supplied afterward,
and their received hashes were separately confirmed by the coordinator.
All copied hashes were checked against the supplied bytes. Existing images and
historical records below retain their own capture methods and identities.

## Reorganized Settings menu — November 24, 2026

`settings.png`, `carplay-android-auto.png`, `audio-sources-menu.png`,
`developer-options.png` and `startup-optimizations-confirm.png` are **unedited
native 800×480** captures of **0.3.0-dev.19** on **74.00.324A NA/cmu150_NA**,
reviewed for personal information, credentials, clipping and diagnostic
overlays. Captured after a normal UI Update (`dev.18 → dev.19`) on kernel boot
ID `4311a3f8…`, with Base/Startup optimizations, Wireless CarPlay and Show
CarPlay on connection enabled. These are software UI verification captures on
the bench, separate from real-car and physical Commander Dial qualification.

Build: [CI 45542133658](https://github.com/aeharding/open-connect/actions/runs/45542133658),
source [3a71ac10](https://github.com/aeharding/open-connect/tree/3a71ac105bf4bb006f6857925389fc7762529317).
USB installer ZIP SHA256:
`e885b78d88a011dba3d25a28dddadb0a77a5be5af93825fe10c8a43ebf054021`.
All 47 public payload manifest hashes matched.

| Asset | SHA256 |
| --- | --- |
| `settings.png` | `e594f37127607e3df59509b5c1b171568546ad67de8e392bc81002067d24e46c` |
| `carplay-android-auto.png` | `6c4dca2e8c7add07d2db9e7f8de6f8024c78ab4fa59f3a2ea5a93af647a6406f` |
| `audio-sources-menu.png` | `6f1dfe5fb28febd1bfbd1aedff130aff12b45476d4b3c1260ee4ff43386c74d0` |
| `developer-options.png` | `b8f3294fe5c8b640a93e8a2307dd06e50eea19ac25f518821093d5af5cd53e04` |
| `startup-optimizations-confirm.png` | `bcd6d1abcf18ad87f6d453febed37cff30db7296b263e7e2f02515842ea9b7cd` |

Private originals: `runs/dev19-car-test-20261124/{settings-top.png,carplay-android-auto.png,audio-sources.png,developer-options.png,startup-optimizations-confirm.png}`.

## Version Information — November 24, 2026

`version-info.png` is a direct, unedited native **800×480** capture of Mazda’s
**Settings → System → About → Version Information** dialog on
**74.00.324A NA/cmu150_NA**, supplied by the capture operator and independently
checked against the received hash. It shows **OS Version 74.00.324 NA N**,
**Music Database Version 00.12.003** and **Fail-Safe Version 74.00.324**.
The full image was reviewed for VIN, serial numbers, personal information,
credentials and diagnostic overlays; none are visible. The decorative bezel is
applied separately by the website.

| Asset | SHA256 |
| --- | --- |
| `version-info.png` | `a84286239850a09c81a48a91543d4b3a0286b8b18065fa8392fc274906569117` |

Received original: `runs/docs-brand-preview/version-info.png`. This documents
firmware identity, not a new installer or real-car qualification.

## Animated maintenance dialogs — November 24, 2026

The current `install.png`, `installing.png`, `complete.png`, `update.png`,
`uninstall.png`, `restarting.png`, `settings.png` and `base-enable.png` are
**unedited native 800×480** captures of the **0.3.0-dev.17** client on
**74.00.324A NA/cmu150_NA**, reviewed for personal information, credentials and
diagnostic overlays. The Update chooser shows the actual dev.16→dev.17 decision
before applying the update. Completion is from a later installed boot;
Open settings opened the real installed menu on the initial 533142d6 build;
the corrected build’s pictured Completion was dismissed with Done. The Base confirmation includes
the complete Navigation-delay explanation. Settings removal/restart contains no
USB wording. Manual SD maintenance is separate from physical USB-insertion
qualification and from real-car/physical-commander checks.

Build: [CI 45390881869](https://github.com/aeharding/open-connect/actions/runs/45390881869),
source [533142d6](https://github.com/aeharding/open-connect/tree/533142d67e7a7e79e34abc6bcb87b7b1f5663f73).
Public manifest SHA256:
`56b036f3ed7526706043e75e4b8e7f6854b12f94288c3d97693ea3874d60db80`.
All 46 public payload hashes matched; private instance binding is not published.

**Completion exception:** `complete.png` is the final corrected build,
[ad10c3a](https://github.com/aeharding/open-connect/tree/ad10c3a68084c7d825c8f536c4414d710e908164),
[CI 45405103481](https://github.com/aeharding/open-connect/actions/runs/45405103481).
Its public manifest SHA256 is
`9794c7989454f9ece39a96ad05c80e6c4f653c551c16f93d202638599c40d103`.
It appeared automatically with Base on, before any maintenance reopen or
independent backend status probe. The other images retain source 533142d6.

| Asset | SHA256 |
| --- | --- |
| `install.png` | `5d560d752787e09ea585f4fb1692c01a34ab4aadb97bbe962aec38271e6845a3` |
| `installing.png` | `a676fd1919046b6175541ef9f83d7d1964e2db4c6103e4dc4458eae15bd089aa` |
| `complete.png` | `3182887ad11268e8f61af324cff1735f7daa9abf684babc753f68d097aeb8b94` |
| `update.png` | `eecf6bf729e74306f6c180a40e331685229474f7c301ee89dc3d7f62723a96d2` |
| `uninstall.png` | `158d25f00c9acd465173bd899d1a8c394ed63ffa63c8ea8ac16aac3a213bc250` |
| `restarting.png` | `8b4452d0dbb2a1dad1d62f9d0650db1d7414a7b85a3db2f6ac96e5d23c79e6cb` |
| `settings.png` | `e6a4b90f99f1038596b3a8c3e9ed7dfeebf32c48dcf5e4e4c5eae272212a680d` |
| `base-enable.png` | `77725a92a1c8c1682049229310a3fcf80517e58362bcf2bf524b755aa5bb954a` |

Native capture originals and verification receipts were retained privately.
The restarting capture used a four-second observation-only delay before sending
its single restart request. These lifecycle capture loops were excluded from
normal boot timing/RAM measurements. [The qualification record](../../maintenance-loading.md)
separates actual operations from rare-state layout previews and retains limits.
Older sections below describe superseded image bytes, preserved in Git.

## Sparse native loading candidate — November 24, 2026

The `services.png`, `android-auto-disable.png`, `audio-sources.png`, `update.png` and `complete.png`
captures recorded at this stage are direct, unedited 800×480 native captures of **0.3.0-dev.16** on
**74.00.324A NA/cmu150_NA**, reviewed for personal data, credentials and overlays.
Services and the Android Auto confirmation show Base off, AA/Pandora/SiriusXM on,
and DVD off. Audio Sources shows Base on with AA, DVD, Pandora and SiriusXM off;
its generic phone label contains no owner identity. This non-tuner bench does
not qualify radio or satellite playback. These are software UI checks using the
manual SD maintenance route, separate from physical USB-insertion qualification.

Build: [CI 45336747490](https://github.com/aeharding/open-connect/actions/runs/45336747490),
source [da45ae8](https://github.com/aeharding/open-connect/tree/da45ae8bcc556474b9949025011907e04c63695c).
Public manifest SHA256:
`ab51278b10c59fe3f5a037419f155a63ca94b6198f3d61252852eb56b4c1f2d6`.
All 46 public payload entries matched; INSTANCE binding was added privately.

| Asset | SHA256 |
| --- | --- |
| `services.png` | `b8aa23948ec8b783b820f68dcc4258f48f16ab51e208d0730f3d2717bea88f27` |
| `android-auto-disable.png` | `95603b25a83797ee087aa914b7e8bdda0ed59ec6322680d5e2f29c16a218fb77` |
| `audio-sources.png` | `761879382844206909d4a319e3e28a10e1e164fb2a3418155a331fbb6ae22ea8` |
| `complete.png` | `3b1a9cf0e1b78c596199c22a8759a5d2a45c3bc0bd9acc5a9d44a283ffef7264` |
| `update.png` | `0876a8692089223576841863773205e6bf81446b9b36bc05e668623dabdea01a` |

Private originals: `runs/wave-c-20261123/{dev16-default-services.png,
dev16-aa-disable-popup.png,maxoff-audio-sources.png,dev16-update.png,dev16-complete.png}`. Services/AA were captured
on kernel a7e6fcdd, Sources on d4d9f40b. The update chooser shows the real dev.15→dev.16 transition before installation;
completion is from its new boot and Open settings opened the installed page.
The older per-version records below are
historical provenance; Git retains their superseded image bytes.

<span id="applied-audio-sources-november-23-2026"></span>
<span id="applied-audio-sources--november-23-2026"></span>

## Applied Audio Sources 2026-11-23

`audio-sources.png` is a direct, unedited 800×480 native screenshot of
**0.3.0-dev.15** on **74.00.324A NA/cmu150_NA**. Base is on, Android Auto and
Pandora are on, DVD is off and SiriusXM is on. The native Entertainment list
omits the disabled integrations; enabled sources retain Mazda's availability
rules. This bench has no equipped satellite tuner. The generic device label
and the complete image were reviewed for private information and diagnostic overlays.

Build: [CI 45207857419](https://github.com/aeharding/open-connect/actions/runs/45207857419),
source [7e81225](https://github.com/aeharding/open-connect/tree/7e8122571d241fc3b58d0356687f0932bdacd5d0).
Public manifest SHA256: `0a03f9916cd931ae9aa00c7d4e084b55b29231dc067dfbfc64ab21eb647461dc`.
All 42 public entries matched the installed package; `INSTANCE` was its sole private addition.
The source list was opened through Mazda's existing `SelectEntertainmentNoAudio`
event, without replacing its list builder. It is a software UI check.

| Asset | SHA256 | Kernel boot ID |
| --- | --- | --- |
| `audio-sources.png` | `c3eb0febd00a168fe19bd6714861e0038e960c9dcacfe1fafbfc0c9b9a267d11` | `4311a3f8-6bff-48af-9704-56c22c35b0df` |

Private capture/state receipts: `runs/wave-b-20261123/{ci15-audio-sources-native.png,
ci15-browser-screen.out,ci15-installed-match.json}`.

## Services controls and Base confirmation — November 23, 2026

`services.png` and `base-enable.png` are direct, unedited 800×480 native
screenshots of **0.3.0-dev.15** on **74.00.324A NA/cmu150_NA**, reviewed for
personal data, credentials and diagnostic overlays. They show the fresh defaults
(SiriusXM on, DVD off) and the Base confirmation. Cancel preserved the exact record.

Build: local `make release`, checked against the exact firmware; source
[9b8fe11](https://github.com/aeharding/open-connect/tree/9b8fe119c3efb5dfc3eb8238853bd0ae2d49d068).
Public manifest SHA256: `c995b450d56fa0a9f4434bc2dd7cf60e62782a92cf37980a94532b8a92b2e230`.
All 42 public entries matched the installed package; `INSTANCE` was its sole private addition.
The manual SD bench path was used; these are software UI captures, not a new
physical USB-insertion or tuner/playback qualification.

| Asset | SHA256 | Kernel boot ID |
| --- | --- | --- |
| `services.png` | `bf7f63f3119611521867e0267e742b6d76f00ad9236033970ffddb93bfc2adcd` | `f4954f87-d889-4aa7-83fe-64f025dce083` |
| `base-enable.png` | `e9e79b2742d9c63961cd82d278e3f6fba4fb3ba31586e49142f701ed72260c9f` | `f4954f87-d889-4aa7-83fe-64f025dce083` |

Private capture/state receipts: `runs/wave-b-20261123/{candidate.json,
services-current.png,base-enable-cancel.png,first-screen.out}`. Git retains the
superseded dev.14 Base and dev.10 Services images and their own identities.

## Services candidate captures — November 22, 2026

Direct, unedited 800×480 native screenshots of **0.3.0-dev.10** on exact
**74.00.324A NA/cmu150_NA**, reviewed for personal data and diagnostic overlays.
The update used the manual SD bench path. These images do not establish another
physical USB-insertion test or Android-phone/audio qualification.

Build: [CI 45016577830](https://github.com/aeharding/open-connect/actions/runs/45016577830),
source [0b5a4af7](https://github.com/aeharding/open-connect/tree/0b5a4af74cdf8ab15014b3d6de63671fc4808666),
artifact `14752172587`. Public manifest SHA256:
`fde4ebfd66d79406fc46bf08a39b7ac61d60d098a86f979a57fd7b0ef6376b79`.
All 40 public members matched the installed runtime.

| Asset | SHA256 | Kernel boot ID |
| --- | --- | --- |
| `update.png` | `cb12693f93c74a85de19ba825b4eab6abf28b47b4f848d5d25a54edee76f86cc` | `74bb37d6-af3e-4e4b-a626-e2fcd183e157` |
| `complete.png` | `42e18f5fd3a876dd314035b774194a5364663d709ad1d3adbe1d0339e775107d` | `1af4801a-632f-4f8d-b9dc-5f9ba8a4b4b0` |
| `android-auto-disable.png` | `1580dcf438ad520fa9f47104689205bb195dc80463ac32f968dbd36821f4a297` | `1af4801a-632f-4f8d-b9dc-5f9ba8a4b4b0` |
| `services-disable.png` | `2d5acac03f750b4a9c950afa14d8f7aa6bf56dcea5879e558c9c0cc2b71170f0` | `89cd8079-f85b-4f53-b168-df7c345f6219` |

The update prompt shows dev.10 → dev.10 from a freshly extracted maintenance
payload, before selecting Uninstall. The completion was reopened after returning from CarPlay. Android Auto is on
before its Disable confirmation; Cancel preserved the exact record. Private
capture receipts are under `runs/developer-options-20261120/screens/dev10-*`;
installed-byte verification is `runs/services-pilots-20261122/verify-reviewed-dev10.out`.

## Wireless candidate captures — November 21, 2026

Direct, unedited 800×480 native screenshots of **0.3.0-dev.8** on exact
**74.00.324A NA/cmu150_NA**. Each image was reviewed for private information
and diagnostic overlays. The installer used the manual SD bench path; these
captures do not claim another physical USB-insertion test. Projection camera
frames containing personal maps are excluded.

Build: [CI 44942234519](https://github.com/aeharding/open-connect/actions/runs/44942234519),
source [c25d5202](https://github.com/aeharding/open-connect/tree/c25d5202ddebfed15b2f3eab8cccedb54a244dad),
artifact `14722505940`. Public manifest SHA256:
`3e0d04f7b4af47e0cffffba3ebea52fe8da4631cdb8c1447f77ddd2436948150`.
All 37 public manifest entries matched the installed runtime.

| Asset | SHA256 | Kernel boot ID |
| --- | --- | --- |
| `install.png` | `ddc99e8d50f4fb7b949c575aeebc7fa5f747270e54c79a5c9c4c758f5cb86b44` | `e6ddc423-32a8-457f-9006-3082ccffe4a8` |
| `settings.png` | `57a8fba7e40411da5d7834e8de7a5a063890aee53bb1cddc06e9acaf1cfb59c4` | `6a2d8cdd-d02a-4b41-8887-29011828d174` |
| `developer-options.png` | `aebf7a8f2f3af64ca2bede54be85e073f351d2626137a499af541cdb28dc57d5` | `6a2d8cdd-d02a-4b41-8887-29011828d174` |
| `wireless-enable.png` | `78d7e13b282e0c318771b26711a28bec7cb1a6a3fe76aeb9bc272a7b093e15b8` | `5da37953-7834-4b4f-9034-2cd9629713f0` |
| `wireless-mode.png` | `893b89fda697538454e82f18e303c86537cb768e90273606d902fe8f081701b6` | `73bed4dd-ea34-4643-8b95-0cbb7b000caa` |
| `wireless-disable.png` | `26868024b5fed5bbc5cf25bd164d55b205aaf79a45f4f45505b962955cccb311` | `42973c02-218c-4ed9-ae04-abe41dbdeafa` |
| `uninstall.png` | `caeb73317badc550e412a4317e72ab8e1b0c110e70ed135458324b26908150f0` | `8f2fbbb9-3fab-4a12-b1f9-67d19f19336d` |

The install prompt and Settings
pages show dev.8 fresh defaults: Allow/Skip selected, Wireless/Base/UART/SSH off and
Pandora on. Wireless confirmations precede their writes; the mode selector is
Mazda’s native Wi-Fi page. The uninstall confirmation was opened from the installed
menu with Wireless enabled.

Private receipts: `runs/wireless-enable-20261121/{ci-r1/identity.json,
dev8-upgrade-check.out,fresh-dev8-check.out,final-uninstall/closure-stock.json}`
and `runs/developer-options-20261120/screens/wireless-dev8-*` capture/hash receipts.
These replace older installer/menu screenshots; Git preserves their provenance.
