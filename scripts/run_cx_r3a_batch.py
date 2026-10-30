#!/usr/bin/env python3
"""Launch a reproducible CX batch: Particle-1 with the R3-A detect-only harness.

The launcher deliberately requires ``--confirm-paid-run`` before it can contact
OpenRouter.  Without that flag it prints the exact Harbor command, making it
safe to inspect the 40-task setup first.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TUA_ROOT = ROOT / "vendor" / "TUA-Bench"
FR_ROOT = ROOT / "contributions" / "yichen-tang" / "failure_recovery"
TASK_LIST = ROOT / "configs" / "task_list_40.txt"
DEFAULT_MODEL = "openrouter/particle-ai/particle-1"


def load_dotenv(path: Path) -> None:
    """Load simple dotenv entries without printing secret values."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def canonical_tasks() -> list[str]:
    return [line.strip() for line in TASK_LIST.read_text().splitlines() if line.strip() and not line.startswith("#")]


def command(args: argparse.Namespace, tasks: list[str], job_name: str) -> list[str]:
    cmd = [
        "uv", "run", "harbor", "run",
        "--job-name", job_name,
        "--jobs-dir", str((ROOT / args.output_root).resolve()),
        "--n-concurrent", "1",
        "--max-retries", "0",
        "--yes",
        "--path", "tasks",
        "--agent-import-path", "failure_recovery_harbor:FailureRecoveryMiniSweAgent",
        "--model", args.model,
        "--agent-kwarg", "version=2.4.3",
        "--agent-kwarg", f"config_file={FR_ROOT / 'failure-recovery-ablation.yaml'}",
        "--agent-kwarg", f"cost_limit={args.cost_limit:.2f}",
    ]
    for task in tasks:
        cmd.extend(["--include-task-name", task])
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", action="append", help="Task ID; repeat to run a selected ordered subset.")
    parser.add_argument("--all", action="store_true", help="Select the canonical 40-task list.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cost-limit", type=float, default=0.10)
    parser.add_argument("--output-root", default="runs/cx-r3-a")
    parser.add_argument("--job-name", default=None)
    parser.add_argument("--confirm-paid-run", action="store_true")
    args = parser.parse_args()

    if bool(args.task) == args.all:
        parser.error("choose exactly one of --task (repeatable) or --all")
    if not FR_ROOT.is_dir():
        parser.error(f"R3-A source is missing: {FR_ROOT}")
    if not TUA_ROOT.is_dir():
        parser.error(f"TUA-Bench checkout is missing: {TUA_ROOT}")
    tasks = canonical_tasks() if args.all else args.task
    unknown = sorted(set(tasks) - set(canonical_tasks()))
    if unknown:
        parser.error(f"task(s) are not in the canonical 40-task list: {', '.join(unknown)}")

    load_dotenv(ROOT / ".env")
    if args.confirm_paid_run and not os.environ.get("OPENROUTER_API_KEY"):
        parser.error("OPENROUTER_API_KEY is missing from the environment/.env")
    job_name = args.job_name or f"cx-r3a-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    cmd = command(args, tasks, job_name)
    print("CX harness: R3-A detect-only (fr_detect=true; fr_salvage=false)")
    print(f"Model: {args.model}; tasks: {len(tasks)}; per-task cap: ${args.cost_limit:.2f}")
    print("Command:")
    print(" ".join(cmd))
    if not args.confirm_paid_run:
        print("Dry configuration check only. Add --confirm-paid-run to start billed model tasks.")
        return 0

    env = os.environ.copy()
    env["DOCKER_DEFAULT_PLATFORM"] = "linux/amd64"
    env["PYTHONPATH"] = str(FR_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(cmd, cwd=TUA_ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
