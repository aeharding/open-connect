"""Build the bounded ARM loopback receiver; no CMU operations."""

import argparse
from pathlib import Path

from open_connect.paths import ROOT

from .build_flush import build

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    build(a.output, ROOT / "cmu/startup/ready-receiver.c", "ready-receiver-arm")
