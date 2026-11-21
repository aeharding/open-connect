# Guide image provenance

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
| `complete.png` | `275baee336d337b726d4b38a5d646754d4c9cb70efe2092a829e8c8697c7e2e2` | `6a2d8cdd-d02a-4b41-8887-29011828d174` |
| `update.png` | `e4c65cd9c43a9a9a52b255eade2012a3199392c2192b98ada4183dffe0edc026` | `cdf11517-e8c7-4f6b-8bc9-f2afec2c9666` |
| `settings.png` | `57a8fba7e40411da5d7834e8de7a5a063890aee53bb1cddc06e9acaf1cfb59c4` | `6a2d8cdd-d02a-4b41-8887-29011828d174` |
| `services.png` | `49fc519c7725552bfc2e81ab188fe75b67e2cbe56cb8194262990ba657a7ec41` | `6a2d8cdd-d02a-4b41-8887-29011828d174` |
| `developer-options.png` | `aebf7a8f2f3af64ca2bede54be85e073f351d2626137a499af541cdb28dc57d5` | `6a2d8cdd-d02a-4b41-8887-29011828d174` |
| `wireless-enable.png` | `78d7e13b282e0c318771b26711a28bec7cb1a6a3fe76aeb9bc272a7b093e15b8` | `5da37953-7834-4b4f-9034-2cd9629713f0` |
| `wireless-mode.png` | `893b89fda697538454e82f18e303c86537cb768e90273606d902fe8f081701b6` | `73bed4dd-ea34-4643-8b95-0cbb7b000caa` |
| `wireless-disable.png` | `26868024b5fed5bbc5cf25bd164d55b205aaf79a45f4f45505b962955cccb311` | `42973c02-218c-4ed9-ae04-abe41dbdeafa` |
| `uninstall.png` | `caeb73317badc550e412a4317e72ab8e1b0c110e70ed135458324b26908150f0` | `8f2fbbb9-3fab-4a12-b1f9-67d19f19336d` |

The update prompt shows dev.7 → dev.8. Install/completion and the three settings
pages show fresh defaults: Allow/Skip selected, Wireless/Base/UART/SSH off and
Pandora on. Wireless confirmations precede their writes; the mode selector is
Mazda’s native Wi-Fi page. The uninstall confirmation was opened from the installed
menu with Wireless enabled.

Private receipts: `runs/wireless-enable-20261121/{ci-r1/identity.json,
dev8-upgrade-check.out,fresh-dev8-check.out,final-uninstall/closure-stock.json}`
and `runs/developer-options-20261120/screens/wireless-dev8-*` capture/hash receipts.
These replace older installer/menu screenshots; Git preserves their provenance.

## Retained service confirmations — November 21, 2026

`base-enable.png` and `services-disable.png` retain their direct, unedited
**0.3.0-dev.7** screenshots on the same exact firmware. Their UI is unchanged.

| Asset | SHA256 | Kernel boot ID |
| --- | --- | --- |
| `base-enable.png` | `1a2acfa3c615321d309a7a2e28567dd47a7fea6699ce43a86b3454c1203a96b5` | `20262390-8431-4cce-a2be-192d3b7bbdea` |
| `services-disable.png` | `8a294005e92cf17791feede7c8e13342fe0b5cd17a474ce3b8f26fef8bcea65d` | `dfe4886e-f749-4580-80ef-b1fba20176c2` |

Build: [CI 44917434811](https://github.com/aeharding/open-connect/actions/runs/44917434811),
source [2bbc8ade](https://github.com/aeharding/open-connect/tree/2bbc8ade53ea455bd923c0fd4ae487ee9e93e285),
public manifest `e403bdd466a0e8d15bbcc787fa02268aaae3972fb704f88cb45d7efc6bfa8fed`.
Base is off before its Enable confirmation. Pandora is on before Disable; Cancel
preserved that selection. Private receipts remain in
`runs/base-optimizations-20261121/` and the `base-enable-popup` /
`base-pandora-disable-popup` capture receipts under the screenshot directory above.
