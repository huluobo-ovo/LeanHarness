#!/usr/bin/env python3
"""Apply or restore LeanHarness Role 5's Harbor 0.6.3 adapter integration."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from leanharness.integrations.harbor_role5_patch import apply_patch, restore_patch


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "adapters" / "role5_runtime_agent.py"


def default_adapter_path() -> Path:
    spec = importlib.util.find_spec("harbor.agents.installed.mini_swe_agent")
    if spec is None or spec.origin is None:
        raise RuntimeError("Harbor is not importable. Run this inside the TUA-Bench uv environment.")
    return Path(spec.origin)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "restore"))
    parser.add_argument("--adapter", type=Path, default=None, help="Target Harbor mini_swe_agent.py; defaults to the installed Harbor module.")
    args = parser.parse_args()
    adapter = args.adapter or default_adapter_path()
    if args.action == "apply":
        backup = apply_patch(adapter, RUNTIME)
        print(f"Applied Role 5 integration to {adapter}\nBackup: {backup}")
    else:
        restore_patch(adapter)
        print(f"Restored Harbor adapter from backup: {adapter}")


if __name__ == "__main__":
    main()
