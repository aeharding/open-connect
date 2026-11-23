# Guide image provenance

## Applied Audio Sources — November 23, 2026

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
