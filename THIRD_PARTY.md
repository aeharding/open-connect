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
Wayland display, without cropping or other image edits.
They show Mazda firmware **74.00.324A NA / cmu150_NA**. Each original PNG matches
its received SHA-256 and was reviewed for personal data, credentials and
diagnostic overlays. The separately authored `cmu-frame.svg` is a decorative
bezel displayed around the captures by the website; it is not part of the screen.

- `install.png`, `complete.png`, `settings-entry.png`, `touch.png`, `warning.png`
  and `uninstall.png` show Open Connect **0.3.0-dev.1** from
  [CI run 44716935060](https://github.com/aeharding/open-connect/actions/runs/44716935060),
  source `ba941122b7306136d8f63448085f1e170fcb5afb`. Its USB ZIP SHA-256 is
  `dde586b5072ef4d90a985fa91ebaf054db8c056410ff97585c79dc80cd12276d`.
- `settings.png`, `services.png` and `services-disable.png` show
  **0.3.0-dev.6** from CI run 44893957634, source
  `c98c9ce4f048255805813a9485eedff8bbdd9816`.
  `developer-options.png` retains its **0.3.0-dev.4** identity. These were captured
  November 21, 2026. Their exact package identities and native PNG hashes
  are recorded in the [guide asset notes](docs/assets/guide/README.md).
- `uart-console.png` and `ssh-key-imported.png` show
  **0.3.0-dev.3** from
  [CI run 44856371233](https://github.com/aeharding/open-connect/actions/runs/44856371233),
  source `356cd7e6fe9820c6d2a6b5e6b4daf89ea4411aec`. Its USB ZIP SHA-256 is
  `a9d1b449071be1bc9b7c9d349e2fc7c9dcdfe2f459f5a51b41722f81141344d8`.
  The displayed fingerprint belongs to a dedicated test public key; no private
  key or owner credential is shown.

- `update.png` shows the **0.3.0-dev.4** maintenance client from
  [CI run 44857345909](https://github.com/aeharding/open-connect/actions/runs/44857345909),
  source `17b5715014091d9672a8359b5b0dc99b586fc460`, while the installed package
  is 0.3.0-dev.3. Its USB ZIP SHA-256 is
  `6e6b8d986dc3988d4a2e74488cac5dfff10412a2539797bab5949a3df0ad9b13`.

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
