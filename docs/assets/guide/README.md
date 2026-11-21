# Guide image provenance

## Installer captures — November 21, 2026

Direct, unedited 800×480 screenshots of the **0.3.0-dev.7** CI payload on exact
**74.00.324A NA/cmu150_NA**. The normal dialog was launched through the verified
manual SD bench path; these images do not claim a new physical USB-insertion test.
No personal information or diagnostic overlay is present.

| Asset | SHA256 |
| --- | --- |
| `install.png` | `9d4b57e4d6a0a2492c01e089316d7e847bf9b6f3c9d306ea2c956ab71e28c181` |
| `complete.png` | `e2ea85c09d09e1e551171ddeed9820b50819c2c6d61e4a0f3b09be830b62d57e` |
| `update.png` | `9b6507c70b6f7dc17abd9a256160bc1b7e55e4d423aeccdd0538deb4140b0845` |

Build: [CI 44917434811](https://github.com/aeharding/open-connect/actions/runs/44917434811),
source [2bbc8ade](https://github.com/aeharding/open-connect/tree/2bbc8ade53ea455bd923c0fd4ae487ee9e93e285),
public manifest `e403bdd466a0e8d15bbcc787fa02268aaae3972fb704f88cb45d7efc6bfa8fed`.
Install prompt: original boot `9f06a182-4ba7-43e0-b714-7e2f4aaa7316`.
Completion: fresh installed boot `20262390-8431-4cce-a2be-192d3b7bbdea`.
Update: installed dev.6 → dev.7, boot `70ab108a-e70b-4c4e-8aec-7372ccc52cbc`.
All public payload members were verified before launch; the new installed
runtime/durable package also matched CI after restart.

Private receipts under `runs/base-optimizations-20261121/` include
`ci-initial/identity.json`, `fresh-payload-verified.json`, `legacy-verified.out`,
`prepare-upgrade-media.out` and `launch-upgrade.out`. Original screenshot receipts
are `runs/developer-options-20261120/screens/base-{fresh-install-prompt,completion-current,upgrade-prompt}.*`.
These replace the older dev.1/dev.4 guide images; Git preserves their provenance.

## Base optimizations captures — November 21, 2026

Direct, unedited 800×480 screenshots of installed **0.3.0-dev.7** on exact
**74.00.324A NA/cmu150_NA**, after normal SD installation, automatic restart,
completion and Open settings. Allow/Skip are selected, UART/SSH are off,
Pandora is on and Base is initially off. The enable confirmation precedes the
preference write. No private information or diagnostic overlay is present.

| Asset | SHA256 |
| --- | --- |
| `settings.png` | `24e2825e80220004ab474ceb6e3ad3270e836afa9637722246a95b974f0b9746` |
| `services.png` | `1f4289aa977c5d4a3a5e17869d027acf5c7f3c8ab8bdefe43490a8fad116b0d1` |
| `base-enable.png` | `1a2acfa3c615321d309a7a2e28567dd47a7fea6699ce43a86b3454c1203a96b5` |

Build: [CI 44917434811](https://github.com/aeharding/open-connect/actions/runs/44917434811),
source [2bbc8ade](https://github.com/aeharding/open-connect/tree/2bbc8ade53ea455bd923c0fd4ae487ee9e93e285).
All 34 public members in both runtime and durable payload matched that CI
payload. Generated INSTANCE data was separately checked against the installed
manifest.
Public manifest `e403bdd466a0e8d15bbcc787fa02268aaae3972fb704f88cb45d7efc6bfa8fed`.
Boot `20262390-8431-4cce-a2be-192d3b7bbdea`.

Private receipts: `runs/base-optimizations-20261121/ci-initial/identity.json`,
`fresh-payload-verified.json`, and
`runs/developer-options-20261120/screens/base-{settings-fresh,services-default,enable-popup}.*`.
These replace the dev.6 Settings/Services images; Git preserves those captures.

## Pandora confirmation — November 21, 2026

`services-disable.png` is a direct, unedited **0.3.0-dev.7** capture from the same
CI payload above, after the normal dev.6 → dev.7 upgrade. Base is off and Pandora
has been selected on; the Disable confirmation is captured before its preference
write. Cancel preserved Pandora on. No private information or overlay is present.
SHA256 `8a294005e92cf17791feede7c8e13342fe0b5cd17a474ce3b8f26fef8bcea65d`.
Boot `dfe4886e-f749-4580-80ef-b1fba20176c2`.
Private receipts: `runs/base-optimizations-20261121/upgraded-verified.out`,
`upgraded-enable-pandora-and-open-disable.out`,
`upgraded-cancel-pandora-and-open-base.out`, and
`runs/developer-options-20261120/screens/base-pandora-disable-popup.*`.
This replaces the dev.6 confirmation; Git preserves the previous bytes.

## Menu captures — November 21, 2026

The Developer options image is a direct 800×480 CMU screenshot of the installed **0.3.0-dev.4**
candidate on **74.00.324A NA/cmu150_NA**, captured after normal installation,
automatic restart and Open settings. The two initial features are selected;
UART and SSH are off. It shows the UART and SSH checkboxes and the Import public key action,
without a subpage caret on that action.

| Asset | SHA256 |
| --- | --- |
| `developer-options.png` | `ac495e003ca679a74cc29e27a1e862df365c702d18cb197d9d559476fdf64564` |

Build: [CI 44874819096](https://github.com/aeharding/open-connect/actions/runs/44874819096),
source [3713f240](https://github.com/aeharding/open-connect/tree/3713f240e21f2e7ac40e24c3f4a2083d08994849).
The installed runtime was checked against every member of that CI package.
Public package manifest SHA256:
`caca0596c53b678cc587226a362bce48f04652a65dcd359331ef45415dddd48f`.

Private capture receipts and build/runtime binding:
`runs/startup-comparison-20261121/candidate-identity.json` and
`runs/developer-options-20261120/screens/comparison-{settings,developer}-3713.*`.
The committed images preserve the native screenshot bytes.
