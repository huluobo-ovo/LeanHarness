#!/usr/bin/env python3
"""Run Role 5 Harbor trials sequentially, with one auditable trial per task.

This launcher deliberately never calls ``harbor job resume``.  A task is started
once, the Harbor process is allowed to finish, its artifact is checked, and only
then may the next task start.  This prevents a second dispatcher from creating
duplicate, billable trials for the same task.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


RECORD_HEADERS = [
    "run_date", "configuration", "task_id", "model", "agent_version",
    "adapter_commit", "run_status", "reward", "exception",
    "runtime_seconds", "input_tokens", "output_tokens", "harbor_cost_usd",
    "actual_openrouter_cost_usd", "tool_actions", "guarded_actions",
    "file_not_found", "command_not_found", "permission_denied",
    "timeout_or_exception", "other_failures", "trajectory_path",
    "harbor_output_path", "notes",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without printing secret values."""
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def trajectory_metrics(trial: Path) -> tuple[float, int, int, dict[str, int], str]:
    trajectories = list(trial.rglob("mini-swe-agent.trajectory.json"))
    if len(trajectories) != 1:
        return 0.0, 0, 0, {}, "" if not trajectories else str(trajectories[0])
    data = load_json(trajectories[0])
    messages = data.get("messages", [])
    categories: dict[str, int] = {}
    cost = 0.0
    tool_actions = 0
    guarded = 0
    for message in messages:
        extra = message.get("extra") or {}
        response = extra.get("response") or {}
        usage = response.get("usage") or {}
        cost += usage.get("cost") or 0.0
        category = extra.get("leanharness_category")
        if category:
            tool_actions += 1
            categories[category] = categories.get(category, 0) + 1
        if extra.get("leanharness_guarded"):
            guarded += 1
    return cost, tool_actions, guarded, categories, str(trajectories[0])


def append_record(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECORD_HEADERS)
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in RECORD_HEADERS})


def git_revision(root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False)
    return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"


def build_command(args: argparse.Namespace, task_id: str, trials_dir: Path, trial_name: str) -> list[str]:
    return [
        args.uv, "run", "harbor", "trial", "start",
        "-p", f"tasks/{task_id}",
        "-a", "mini-swe-agent",
        "-m", args.model,
        "--trial-name", trial_name,
        "--trials-dir", str(trials_dir),
        "--agent-kwarg", "version=2.4.3",
        "--agent-kwarg", f"config_file={args.base_config}",
        "--agent-kwarg", f"role5_config_file={args.role5_config}",
        "--agent-kwarg", f"cost_limit={args.cost_limit}",
    ]


def run_one(args: argparse.Namespace, task_id: str, root: Path) -> bool:
    tua_root = root / "vendor" / "TUA-Bench"
    trials_dir = (root / args.output_root / args.configuration.lower() / task_id).resolve()
    trials_dir.mkdir(parents=True, exist_ok=True)
    trial_name = f"{task_id}--{args.configuration.lower()}--{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    trial = trials_dir / trial_name
    log_path = trials_dir / f"{trial_name}.launcher.log"
    command = build_command(args, task_id, trials_dir, trial_name)
    printable = " ".join(command)
    print(f"\n=== {args.configuration} / {task_id} ===\n{printable}", flush=True)
    if args.dry_run:
        return True

    environment = os.environ.copy()
    if args.docker_platform:
        environment["DOCKER_DEFAULT_PLATFORM"] = args.docker_platform
    started = datetime.now()
    with log_path.open("w") as log:
        completed = subprocess.run(command, cwd=tua_root, env=environment, stdout=log, stderr=subprocess.STDOUT, text=True)
    row: dict[str, Any] = {
        "run_date": started.date().isoformat(), "configuration": args.configuration,
        "task_id": task_id, "model": args.model, "agent_version": "2.4.3",
        "adapter_commit": git_revision(root), "harbor_output_path": str(trial),
        "notes": f"launcher_exit_code={completed.returncode}; launcher_log={log_path}",
    }
    if not (trial / "result.json").exists():
        row.update(run_status="infrastructure_failure", exception="YES", timeout_or_exception=1,
                   notes=row["notes"] + "; Harbor did not create a trial result")
        append_record(Path(args.record_csv), row)
        return False

    result = load_json(trial / "result.json")
    cost, actions, guarded, categories, trajectory = trajectory_metrics(trial)
    row.update(
        runtime_seconds=round((datetime.now() - started).total_seconds(), 1),
        harbor_cost_usd=(result.get("agent_result") or {}).get("cost_usd") or 0,
        actual_openrouter_cost_usd=cost, tool_actions=actions, guarded_actions=guarded,
        file_not_found=categories.get("file_not_found", 0),
        command_not_found=categories.get("command_not_found", 0),
        permission_denied=categories.get("permission_denied", 0),
        other_failures=categories.get("other_failure", 0), trajectory_path=trajectory,
    )
    if completed.returncode != 0:
        row.update(run_status="infrastructure_failure", exception="YES", timeout_or_exception=1,
                   notes=row["notes"] + "; Harbor trial process exited non-zero")
        append_record(Path(args.record_csv), row)
        return False
    agent = result.get("agent_result") or {}
    exception = result.get("exception_info")
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward", "")
    row.update(input_tokens=agent.get("n_input_tokens", ""), output_tokens=agent.get("n_output_tokens", ""), reward=reward)
    if exception:
        row.update(run_status="infrastructure_failure", exception="YES", timeout_or_exception=1,
                   notes=row["notes"] + f"; Harbor exception={exception.get('exception_type')}")
        append_record(Path(args.record_csv), row)
        return False
    row.update(run_status="completed", exception="NO")
    append_record(Path(args.record_csv), row)
    return True


def parse_args() -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", choices=("R5-A", "R5-A+B", "R5-B"), required=True)
    parser.add_argument("--task", action="append", required=True, help="Task ID; repeat to run sequentially.")
    parser.add_argument("--model", default="openrouter/minimax/minimax-m3.1-flash")
    parser.add_argument("--cost-limit", type=float, default=0.06)
    parser.add_argument("--docker-platform", default="linux/amd64", help="Use empty string to preserve Docker default.")
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--base-config", default="../../contributions/liu-yalin/developer_pack/settings/mini_base.yaml")
    parser.add_argument("--role5-config", default=None)
    parser.add_argument("--output-root", default="runs/role5-formal")
    parser.add_argument("--record-csv", default=str(root / "results" / "role5" / "formal-results.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.role5_config is None:
        config_files = {
            "R5-A": "../../configs/tool-interface-normalizer.yaml",
            "R5-A+B": "../../configs/tool-interface-complete.yaml",
            "R5-B": "../../configs/tool-interface-command-guard.yaml",
        }
        args.role5_config = config_files[args.configuration]
    return args


def main() -> int:
    args = parse_args()
    root = project_root()
    load_env_file(root / ".env")
    if not args.dry_run and not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is missing; create .env before starting a paid run.", file=sys.stderr)
        return 2
    for task_id in args.task:
        if not run_one(args, task_id, root):
            print(f"Stopped after {task_id}; inspect the recorded infrastructure failure before continuing.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
