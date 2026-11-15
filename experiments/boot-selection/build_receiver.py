"""Build the bounded ARM loopback receiver; no CMU operations."""
from pathlib import Path
import argparse
from build_flush import build

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    build(a.output, Path(__file__).resolve().parents[2] / "cmu/startup/ready-receiver.c",
          "ready-receiver-arm")
