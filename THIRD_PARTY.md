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

## Documentation screenshots

The PNG images in `docs/assets/guide/` were captured directly from the CMU's
native display, without cropping or other image edits. Earlier captures use
Wayland; the `setting-*.png` series uses framebuffer readback.
They show Mazda firmware **74.00.324A NA / cmu150_NA**. Each original PNG matches
its received SHA-256 and was reviewed for personal data, credentials and
diagnostic overlays. The separately authored `cmu-frame.svg` is a decorative
bezel displayed around the captures by the website; it is not part of the screen.

The fourteen `setting-*.png` Commander Dial row captures show **0.3.0-dev.19**,
tag commit `f478f3b282f6987d86e04c03d83b1a6971d5a3db`, supplied on November 24,
2026 as native 800×480 `/dev/fb0` BGRA readbacks. The coordinator identified the
USB bundle SHA-256 as `d4f0feaf4813ef5707d0f2528a0a98b70b571b1def56582b50e35ec463e5048d`.
Each complete image was reviewed for publication; the native red focus was
produced with Commander Dial events, not image edits. Per-file copied hashes
and qualification limits are in the [guide asset notes](docs/assets/guide/README.md#commander-dial-setting-captures-november-24-2026).

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
capture collections and OEM inputs stay private; only these reviewed UI images
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
