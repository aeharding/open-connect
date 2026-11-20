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

The seven PNG images in `docs/assets/guide/` show Open Connect running
on Mazda firmware **55.00.750B NA**. They were captured directly from the CMU's
Wayland display on November 18, 2026, without cropping or other image edits.
Each was reviewed for personal data, credentials and diagnostic overlays.
The separately authored `cmu-frame.svg` is a decorative bezel displayed around
the captures by the website; it is not part of the captured screen.
`install.png` and `complete.png` show **0.2.0-dev.3**, from
[CI run 44368399412](https://github.com/aeharding/open-connect/actions/runs/44368399412)
(source `df7fd03`), with bundle SHA-256
`7490ac35896d71a08b004064b916d7178bdc9f646fa8f5316e30afccfa2172dd`.
The five unchanged Settings/feature/uninstall captures show **0.2.0-dev.2**.
Their USB bundle came from [CI run 44350948917](https://github.com/aeharding/open-connect/actions/runs/44350948917)
(source `2f30ead`), with SHA-256
`98e7e09fdfb8ca87545e481d1276de0a6db28e6a62648f346a5e71b575a300a9`.

The images illustrate installation, completion, the Mazda System menu entry,
Open Connect Settings, the two preferences and uninstall. Mazda's interface appears alongside Open Connect's additions;
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
