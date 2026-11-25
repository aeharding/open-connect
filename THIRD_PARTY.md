# Licensing and third-party material

Original Open Connect code and documentation are licensed under
**GNU AGPL version 3 or (at your option) any later version**, unless a file states
otherwise. See [LICENSE](LICENSE). Copyright 2026 Open Connect contributors.

Mazda firmware, binaries, extracted full JavaScript files, device backups,
private credentials and raw capture collections are not distributed here. Mazda's
UART connection is documented in the bench setup guide.
Local evidence paths and
hashes document research; they are not downloads or grants of rights to OEM code.
Some integration tests require privately obtained exact firmware files and cannot
run from a public checkout alone.

## Documentation screenshots and walkthroughs

The PNG images in `docs/assets/guide/` were captured directly from the CMU's
native display, without cropping or other image edits. Earlier captures use
Wayland; the `setting-*.png` series uses framebuffer readback.
They show Mazda firmware **74.00.324A NA / cmu150_NA**. Each original PNG matches
its received SHA-256 and was reviewed for personal data, credentials and
diagnostic overlays. The separately authored `cmu-frame.svg` is a decorative
bezel displayed around the captures by the website; it is not part of the screen.

### Refreshed Audio sources captures 2026-11-25

`setting-pandora.png` and `setting-siriusxm.png` are unedited native **800×480**
Commander-highlighted captures from the **post-dev.20 PR #149 candidate**,
source `ecddb381185ec4985b87b5ab6acbb3792807fe21`,
[CI 45597702470](https://github.com/aeharding/open-connect/actions/runs/45597702470),
merged as `291492fa4badba2d8479f23add82867d83bf68b6` (`291492fa`).
They match merged main: Pandora and SiriusXM only, both on, **no DVD row**,
with **Bluetooth OFF**. VERSION still reads dev.20; these are not published
release captures or a new performance cohort. Both complete images were
visually reviewed by the operator and documentation implementer: **zero visible
PII**, VIN/unit serials, credentials or diagnostic overlays. Offline byte/hash
checks confirm the supplied originals; raw captures remain private.

| Asset | SHA-256 |
| --- | --- |
| `setting-pandora.png` | `90f9c522c97a251e3c0796dcc8ffb0489a25c95bc3f0b8f285aaf70e707f0670` |
| `setting-siriusxm.png` | `adc2e570d4e47c85bd64d22c130987f66958629309061e5a41da0458fc3a2944` |

Exact private source paths and qualification limits are in the
[guide asset notes](docs/assets/guide/README.md#audio-sources-pr-149-captures-2026-11-25).

### Earlier captures

The fourteen original November 24 `setting-*.png` Commander Dial row captures showed **0.3.0-dev.19**,
tag commit `f478f3b282f6987d86e04c03d83b1a6971d5a3db`, supplied on November 24,
2026 as native 800×480 `/dev/fb0` BGRA readbacks. The coordinator identified
two distinct archive identities. Pandora and SiriusXM are now superseded by the
two PR #149 captures above; unchanged dev.19 images retain this attribution:

- Published GitHub [v0.3.0-dev.19 prerelease](https://github.com/aeharding/open-connect/releases/tag/v0.3.0-dev.19)
  ZIP, as recorded in the release’s `SHA256SUMS`: `c2c09b3123a2145f3582d3ee7f1e692581b1196ab18c5ba60fc198d79716c486`.
- Local coordinator build ZIP: `d4f0feaf4813ef5707d0f2528a0a98b70b571b1def56582b50e35ec463e5048d`.

The coordinator reports that all **50 extracted file members are byte-for-byte
identical** between these archives; the ZIP archive hashes differ.

The documentation implementer copied and hash-checked supplied PNGs offline;
no new live identity or package verification was performed for this docs change.
Each complete image was reviewed for publication; the native red focus was
produced with Commander Dial events, not image edits. Per-file copied hashes
and qualification limits are in the [guide asset notes](docs/assets/guide/README.md#commander-dial-setting-captures-2026-11-24).

The five `docs/assets/guide/walkthroughs/*.mp4` files and
`docs/assets/guide/setting-apply-changes-disabled.png`,
`docs/assets/guide/setting-apply-changes-enabled.png` and
`docs/assets/guide/apply-changes-confirm.png` are reviewed native UI captures
supplied November 25, 2026 from **0.3.0-dev.20** on the same v74 firmware,
exact source `e29b58258c0c9e9f4c4689c7912f634b80008424`,
[CI 45578042314](https://github.com/aeharding/open-connect/actions/runs/45578042314).
All eight files were copied and hash-checked offline. The PNGs are unedited
800×480 captures; the silent MP4s are 800×480, 10 fps, H.264/yuv420p Home-first
Commander Dial walkthroughs. Bluetooth was off during the five MP4 walkthroughs.
The three Apply changes PNGs were captured at 03:06–03:08 CST, before Bluetooth
was turned off at 03:16 CST for the video pass. The operator reviewed every final
clip and PNG for private content and diagnostic overlays; the three PNGs show no
visible personal identifiers. Torn framebuffer samples hold the previous intact
native frame at the original timestamp;
no waits were cut or accelerated. Lossy video pixel identity is not claimed.
These are walkthroughs, not performance timing evidence. Exact hashes and
capture limits are in the
[dev.20 media notes](docs/assets/guide/README.md#commander-dial-mp4-walkthroughs-and-apply-changes-2026-11-25).
This extends only the reviewed native UI capture scope; it does not include
raw masters, general capture collections or OEM asset/source packages.

Current dev.17 Install, loading/restart, Update, Settings, Uninstall
and Base-confirmation captures use
[CI 45390881869](https://github.com/aeharding/open-connect/actions/runs/45390881869),
source `533142d67e7a7e79e34abc6bcb87b7b1f5663f73`. Completion uses the corrected
[CI 45405103481](https://github.com/aeharding/open-connect/actions/runs/45405103481),
source `ad10c3a68084c7d825c8f536c4414d710e908164`. Retained dev.16 Services,
Android Auto and Audio Sources images use
[CI 45336747490](https://github.com/aeharding/open-connect/actions/runs/45336747490),
source `da45ae8bcc556474b9949025011907e04c63695c`. The dev.10 Pandora and
dev.8 Developer/wireless images retain their own identities. Per-file capture
dates, exact hashes and superseded image records are in the
[guide asset notes](docs/assets/guide/README.md). Replacing an image does not
relabel unchanged captures or historical evidence.

Unchanged earlier captures retain these identities:

- `settings-entry.png`, `touch.png` and `warning.png` show Open Connect **0.3.0-dev.1** from
  [CI run 44716935060](https://github.com/aeharding/open-connect/actions/runs/44716935060),
  source `ba941122b7306136d8f63448085f1e170fcb5afb`. Its USB ZIP SHA-256 is
  `dde586b5072ef4d90a985fa91ebaf054db8c056410ff97585c79dc80cd12276d`.
- `uart-console.png` and `ssh-key-imported.png` show
  **0.3.0-dev.3** from
  [CI run 44856371233](https://github.com/aeharding/open-connect/actions/runs/44856371233),
  source `356cd7e6fe9820c6d2a6b5e6b4daf89ea4411aec`. Its USB ZIP SHA-256 is
  `a9d1b449071be1bc9b7c9d349e2fc7c9dcdfe2f459f5a51b41722f81141344d8`.
  The displayed fingerprint belongs to a dedicated test public key; no private
  key or owner credential is shown.

These illustrate the v74 development candidate's UI from bench sessions. They do
not establish physical USB launch or matching-car qualification; no qualified v74
download has been published. Raw
capture collections and OEM inputs stay private; only the reviewed UI images and walkthroughs
are included in the owner guide.

Mazda's interface appears alongside Open Connect's additions. This documentation
does not grant rights to Mazda's underlying interface or redistribute its source
files or asset packages.

## USB bootstrap

The USB trigger filename in `cmu/installer/usb-root/` is adapted from
[Kenatia/mazda-cmu150-wcp-mod](https://github.com/Kenatia/mazda-cmu150-wcp-mod/tree/2069d1e6de20a37ef17654cb5a2fcfa9a4ffdddf),
under MIT, copyright 2026 Loc Le Van. The full notice is preserved in
`cmu/installer/KENATIA-LICENSE` and included in release bundles.
The Open Connect launcher and UI payload are original AGPL-3.0-or-later code.
No CarPlay patches or reconstructed OEM files are included.

## Development checks

The optional Node.js UI checks use [Acorn](https://github.com/acornjs/acorn)
8.15.0, under MIT, to parse target JavaScript as ES5. Its version and package
integrity are pinned in `package-lock.json`; its license stays in the installed
development dependency. Acorn is not included in CMU release bundles.

## Comparison research

The inspected [piotrmocko/mzd-v74-tweaks](https://github.com/piotrmocko/mzd-v74-tweaks)
revision is `5a17963a8631b3b68b9187b6ebbefeef1def05ef`, licensed
CC BY-NC-SA 4.0. Our local comparison and Snap adaptations retain
that upstream license and attribution. They are excluded from this repository,
not relicensed under AGPL. Published comparison notes describe the approaches;
the independent native implementation predates examination of that code.

Do not copy these local adaptations into AGPL releases. Any future use needs a
compatible permission or an independently designed implementation with documented
provenance. Existing third-party notices and licenses must be preserved.
