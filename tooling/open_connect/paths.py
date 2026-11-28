"""Source assets and the installed host package must describe the same code."""

import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("OC_WORKSPACE", PACKAGE.parents[1])).resolve()


def verify_package(workspace):
    """Refuse a different checkout before recording or executing its workflow."""
    expected = Path(workspace) / "tooling/open_connect"
    actual = {p.relative_to(PACKAGE) for p in PACKAGE.rglob("*.py")}
    recorded = {p.relative_to(expected) for p in expected.rglob("*.py")}
    if actual != recorded:
        raise ValueError(
            "installed host package differs from workspace; reinstall from that checkout"
        )
    for name in actual:
        if (PACKAGE / name).read_bytes() != (expected / name).read_bytes():
            raise ValueError("installed host package differs from workspace: " + str(name))
