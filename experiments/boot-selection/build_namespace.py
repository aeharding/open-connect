#!/usr/bin/env python3
"""Build the Linux ARM namespace probe with the same toolchain as flush."""
import argparse
from pathlib import Path

from build_flush import build

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, Path(__file__).with_name("namespace.c"), "namespace-arm")
