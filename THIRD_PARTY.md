# Licensing and third-party material

Original Open Connect code and documentation are licensed under
**GNU AGPL version 3 or (at your option) any later version**, unless a file states
otherwise. See [LICENSE](LICENSE). Copyright 2026 Open Connect contributors.

Mazda firmware, binaries, extracted full JavaScript files, device backups,
credentials and raw capture collections are not distributed here. Local evidence paths and
hashes document research; they are not downloads or grants of rights to OEM code.
Some integration tests require privately obtained exact firmware files and cannot
run from a public checkout alone.

## Documentation screenshots

The six images in `docs/assets/guide/` show Open Connect **0.2.0-dev.1** running
on Mazda firmware **55.00.750B NA**. They were captured directly from the CMU's
Wayland display on November 18, 2026, without cropping or other image edits.
Each was reviewed for personal data, credentials and diagnostic overlays.
The published USB bundle used for capture has SHA-256
`9555de935513672e2363898ff8d611d868d421501b399a6865587e6ec86eb8d1`.

The images illustrate installation, completion, Settings, the two preferences
and uninstall. Mazda's interface appears alongside Open Connect's additions;
this documentation does not grant rights to Mazda's underlying interface or
redistribute its source files or asset packages.

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
CC BY-NC-SA 4.0. Our local firmware55 comparison and Snap adaptations retain
that upstream license and attribution. They are excluded from this repository,
not relicensed under AGPL. Published comparison notes describe the approaches;
the independent native implementation predates examination of that code.

Do not copy these local adaptations into AGPL releases. Any future use needs a
compatible permission or an independently designed implementation with documented
provenance. Existing third-party notices and licenses must be preserved.
