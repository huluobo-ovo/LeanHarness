#!/usr/bin/env python3
"""Summarize pre-registered Role 5 metrics from task-level CSV records."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from leanharness.analysis.role5_results import summarize


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.input.open(newline="") as source:
        summary = summarize(list(csv.DictReader(source)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
