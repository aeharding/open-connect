"""Build the v55 USB-to-native-dialog experiment; no device operations."""

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from .firmware55.build_flush import build as build_arm
from .paths import ROOT, verify_package

# Adapted from Kenatia/mazda-cmu150-wcp-mod, revision 2069d1e.
# The separator avoids '/' in the filename. Only our own package is considered.
TRIGGER = (
    "$(S=${HOME%root}; for D in sda1 sdb1 sdc1 sdd1; do "
    "P=${S}tmp${S}mnt${S}$D; I=$P${S}open-connect${S}run.sh; "
    "[ -f $I ] && { sh $I; break; }; done).up"
)


def build(output, workspace=ROOT):
    workspace = workspace.resolve()
    verify_package(workspace)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    build_arm(output / "build", workspace / "cmu/startup/ready-receiver.c", "receiver")
    assets = workspace / "cmu/installer"
    package = output / "usb/open-connect"
    package.mkdir(parents=True)
    ui = "(function (token, port) {\n" + (assets / "dialog.js").read_text()
    ui += "\n" + (assets / "usb-preview.js").read_text()
    ui += '\n})(document.getElementById("oc-usb-loader").ocToken, '
    ui += 'document.getElementById("oc-usb-loader").ocPort);\n'
    (package / "ui.js").write_text(ui)
    shutil.copyfile(assets / "usb-session.sh", package / "session.sh")
    shutil.copyfile(output / "build/receiver", package / "receiver")
    checks = []
    for name in ("ui.js", "session.sh", "receiver"):
        digest = hashlib.sha256((package / name).read_bytes()).hexdigest()
        checks.append(
            f'test "$(openssl dgst -sha256 < "$work/{name}")" = '
            f"'(stdin)= {digest}' || refuse checksum"
        )
    launcher = (assets / "usb-launch.sh.in").read_text().replace("@CHECKS@", "\n".join(checks))
    (package / "run.sh").write_text(launcher)
    # Mazda searches the USB root. run_triggers/ is upstream's source layout.
    triggers = output / "usb"
    (triggers / "jci-autoupdate").touch()
    (triggers / TRIGGER).touch()
    shutil.copyfile(workspace / "LICENSE", package / "LICENSE")
    shutil.copyfile(assets / "KENATIA-LICENSE", package / "KENATIA-LICENSE")
    files = sorted(p for p in (output / "usb").rglob("*") if p.is_file())
    archive = output / "open-connect-usb-preview.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(output / "usb").as_posix())
            info.external_attr = 0o100644 << 16
            z.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    manifest = {
        str(p.relative_to(output / "usb")): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }
    (output / "files.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build-preview"])
    parser.add_argument("--workspace", type=Path, default=ROOT, help="matching source checkout")
    parser.add_argument("--output", type=Path, required=True, help="new local build directory")
    args = parser.parse_args(argv)
    print(build(args.output, args.workspace))
    return 0
