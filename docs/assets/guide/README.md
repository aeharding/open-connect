# Guide image provenance

## Services captures — November 21, 2026

Direct, unedited 800×480 screenshots of installed **0.3.0-dev.6** on exact
**74.00.324A NA/cmu150_NA**, after normal SD installation, automatic restart,
completion and Open settings. Allow/Skip are selected, UART/SSH are off and
Pandora initially runs. The confirmation is captured before any preference write.
No private information or diagnostic overlay is present.

| Asset | SHA256 |
| --- | --- |
| `settings.png` | `6c4539cc87cad1107c0d81bfb5be53316ce0f04d918d8e33f50e61288d0eccd5` |
| `services.png` | `196860674d4bce118f09077ee8bc22681a910b92b1ea2b80459314dd9f772b25` |
| `services-disable.png` | `afecb9291ecdf1d883c0b556cfbeba1f3a313eb4552bb233a0f49f4904444a31` |

Build: [CI 44893957634](https://github.com/aeharding/open-connect/actions/runs/44893957634),
source [c98c9ce4](https://github.com/aeharding/open-connect/tree/c98c9ce4f048255805813a9485eedff8bbdd9816).
All runtime members and actual native mappings were verified against that package.
Public manifest `ff3032883f80a7e8aa7fc8fcc74ce75f1e346ec4248082b7f7f170132675817d`.
Boot `a1ad4b9b-fbb4-44dd-8ada-e1b330e2602f`.

Private receipts: `runs/services-20261121/candidate/identity.json`,
`verify-candidate.out` and
`runs/developer-options-20261120/screens/services-dev6-{settings,services-on,disable-prompt}.*`.
The new Settings image replaces its dev.4 predecessor; Git preserves that capture.
The Developer image below retains its actual older identity.

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
