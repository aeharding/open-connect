# Guide image provenance

## Menu captures — November 21, 2026

These are direct 800×480 CMU screenshots of the installed **0.3.0-dev.4**
candidate on **74.00.324A NA/cmu150_NA**, captured after normal installation,
automatic restart and Open settings. The two initial features are selected;
UART and SSH are off. The images show the current caret behavior: subpages have
carets; Uninstall, About and Import public key do not.

| Asset | SHA256 |
| --- | --- |
| `settings.png` | `719ebb16710454002cd4a7eeed199791941161adea107eb5dc4589f8c41b9dd4` |
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
