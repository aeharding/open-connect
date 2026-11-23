# Guide image provenance

## Base confirmation — November 23, 2026

`base-enable.png` is a direct, unedited 800×480 native screenshot of
**0.3.0-dev.14** on **74.00.324A NA/cmu150_NA**, reviewed for personal data,
credentials and diagnostic overlays. Cancel preserved the saved choice.
Build: [CI 45157300285](https://github.com/aeharding/open-connect/actions/runs/45157300285),
source [1e4a26c](https://github.com/aeharding/open-connect/tree/1e4a26c4cbcee3f1383d4a418819716a5927a73f).
Public manifest SHA256: `5d1da1e3d3051ae88c754b547bee9ad3f75ba4cd4c7a023a30869e5fab2c18b5`.
All 43 public members matched the installed package.
PNG SHA256: `5e58ae59428885831bfed92ec067d6664542b62dd60a3332bc144681dc019b27`.
Kernel boot ID: `412b49c5-2e0b-45fa-836c-5689db1de70c`.
This replaces only the Base confirmation; other captures keep their own identities.

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
| `services.png` | `5ac658cca88612ebed4814925d8eb98fc5157dcb1fa95e2db9194b64b4d3b6ea` | `7d69a472-ffd0-474e-966f-34515dd9123b` |

The update prompt shows dev.10 → dev.10 from a freshly extracted maintenance
payload, before selecting Uninstall. The completion was reopened after returning from CarPlay. Android Auto is on
before its Disable confirmation; Cancel preserved the exact record. Services was
configured to the fresh defaults: Base off and both integrations on. Base Enable
was cancelled without changing the record. Private
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
