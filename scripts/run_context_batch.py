#!/usr/bin/env python3
"""Run one Scheme A configuration sequentially through Harbor 0.6.3.

No model or container starts unless --live is supplied.  Each task gets a
separate raw Harbor trial, launcher log, manifest, and CSV record.  This script
does not upload anything or read an API key's value into its output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TUA_COMMIT = "3497fd320abcafaf4797424192c891a593fd7964"
CANONICAL_TASKS = ROOT / "contributions/liu-yalin/developer_pack/settings/task_list_40.txt"
BASE_CONFIG = ROOT / "contributions/liu-yalin/developer_pack/settings/mini_base.yaml"
CONFIGS = {key: ROOT / f"configs/context-{key}.yaml" for key in ("A", "B", "AB")}
CODE_FILES = (
    ROOT / "adapters/context_runtime_agent.py",
    ROOT / "src/leanharness/integrations/harbor_context_patch.py",
    ROOT / "scripts/manage_context_harbor_adapter.py",
    ROOT / "scripts/run_context_batch.py",
)
HEADERS = (
    "suite", "config_id", "task_id", "run_id", "status", "reward", "steps", "wall_time_s",
    "agent_tokens_in", "agent_tokens_out", "agent_cached_tokens", "harness_tokens_in",
    "harness_tokens_out", "agent_usd", "harness_usd", "cost_status", "termination_reason",
    "source_commit", "code_sha256", "base_config_sha256", "variant_config_sha256",
    "model", "exception", "log_path", "trajectory_path", "trial_path", "manifest_path",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_sha256() -> str:
    digest = hashlib.sha256()
    for path in CODE_FILES:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def source_commit() -> str:
    lock = ROOT / "source_lock.json"
    if lock.exists():
        return str(json.loads(lock.read_text()).get("commit") or "")
    return ""


def tua_commit(root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def harbor_version() -> str:
    try:
        return importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def read_task_list(path: Path) -> list[str]:
    tasks = [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not tasks or len(tasks) != len(set(tasks)):
        raise ValueError("task list is empty or has duplicate IDs")
    if any("/" in task or ".." in task or task.startswith("-") for task in tasks):
        raise ValueError("task list contains an unsafe task ID")
    return tasks


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def trajectory_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"cost_status": "missing_trajectory"}
    data = load_json(path)
    messages = data.get("messages") or []
    usages = []
    for message in messages:
        response = ((message.get("extra") or {}).get("response") or {})
        if isinstance(response, dict) and response:
            usage = response.get("usage") or {}
            usages.append(usage if isinstance(usage, dict) else {})
        elif response:
            usages.append({})
    if not usages:
        return {"cost_status": "missing_usage"}
    complete = all(
        isinstance(u.get("prompt_tokens"), int)
        and isinstance(u.get("completion_tokens"), int)
        and isinstance(u.get("cost"), (int, float))
        and math.isfinite(float(u["cost"]))
        and float(u["cost"]) >= 0
        for u in usages
    )
    costs = [float(u["cost"]) for u in usages] if complete else []
    positive = complete and sum(costs) > 0
    totals: dict[str, Any] = {
        "steps": ((data.get("info") or {}).get("model_stats") or {}).get("api_calls", ""),
        "termination_reason": (data.get("info") or {}).get("exit_status", ""),
        "cost_status": "complete" if complete and positive else "missing_or_zero_usage_cost",
    }
    if complete:
        totals.update(
            agent_tokens_in=sum(int(u["prompt_tokens"]) for u in usages),
            agent_tokens_out=sum(int(u["completion_tokens"]) for u in usages),
            agent_cached_tokens=sum(int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0) for u in usages),
            harness_tokens_in=0,
            harness_tokens_out=0,
        )
    if complete and positive:
        totals.update(agent_usd=round(sum(costs), 10), harness_usd=0.0)
    return totals


def append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        if fresh:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in HEADERS})


def duration_text(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s" if hours else f"{minutes}m {seconds:02d}s"


def progress_text(completed: int, total: int) -> str:
    width = 20
    filled = width * completed // total
    return f"[{'#' * filled}{'-' * (width - filled)}] {completed}/{total} ({completed / total:.0%})"


def run_with_heartbeat(command: list[str], cwd: Path, log_path: Path, interval: float, task: str) -> int:
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, text=True)
        while True:
            try:
                return process.wait(timeout=interval)
            except subprocess.TimeoutExpired:
                print(f"  {task} still running; elapsed {duration_text(time.monotonic() - started)}; log: {log_path}", flush=True)


def command_for(args: argparse.Namespace, task: str, run_id: str, trials_dir: Path) -> list[str]:
    command = [
        args.uv, "run", "harbor", "trial", "start", "-p", f"tasks/{task}",
        "-a", "mini-swe-agent", "-m", args.model,
        "--trial-name", run_id, "--trials-dir", str(trials_dir),
        "--agent-kwarg", "version=2.4.3",
        "--agent-kwarg", f"config_file={BASE_CONFIG}",
        "--agent-kwarg", f"cost_limit={args.cost_limit}",
    ]
    if args.configuration != "C0":
        command.extend(["--agent-kwarg", f"context_config_file={CONFIGS[args.configuration]}"])
    return command


def prior_action(args: argparse.Namespace, task: str, record_path: Path) -> str:
    """Skip only a verified completed trial; never silently repeat a paid task."""
    task_root = args.run_root / args.suite / args.configuration / task
    rows: list[dict[str, str]] = []
    if record_path.exists():
        with record_path.open(newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if row.get("suite") == args.suite
                    and row.get("config_id") == args.configuration and row.get("task_id") == task]
    if any(Path(row.get("trial_path") or ".").parent != task_root for row in rows):
        raise RuntimeError(f"record contains {task} from another run root; keep each formal batch in one run root")
    has_files = task_root.exists() and any(task_root.iterdir())
    if not rows:
        if has_files:
            raise RuntimeError(f"trial files exist without a CSV record for {task}; inspect before rerunning: {task_root}")
        return "run"
    if not args.resume:
        raise RuntimeError(f"prior result exists for {task}; use --resume after inspection: {record_path}")
    latest = rows[-1]
    if not has_files:
        raise RuntimeError(f"CSV result exists but trial files are missing for {task}: {task_root}")
    if latest.get("status") == "completed" and latest.get("cost_status") == "complete":
        manifest_path = Path(latest.get("manifest_path") or "")
        trajectory_path = Path(latest.get("trajectory_path") or "")
        if not manifest_path.is_file() or not trajectory_path.is_file():
            raise RuntimeError(f"completed {task} is missing its manifest or trajectory")
        manifest = load_json(manifest_path)
        expected = {
            "suite": args.suite, "configuration": args.configuration, "task_id": task,
            "model": args.model, "source_commit": source_commit(),
            "tua_commit": tua_commit(args.tua_root), "code_sha256": code_sha256(),
            "base_config_sha256": sha256_file(BASE_CONFIG),
            "variant_config_sha256": sha256_file(CONFIGS[args.configuration]) if args.configuration != "C0" else "",
            "task_list_sha256": sha256_file(CANONICAL_TASKS),
            "docker_default_platform": os.environ.get("DOCKER_DEFAULT_PLATFORM", ""),
            "cost_limit_usd": args.cost_limit,
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"settings or code changed since completed {task}; do not mix runs in one formal batch")
        try:
            charged = float(latest.get("agent_usd") or "nan")
        except ValueError:
            charged = math.nan
        if not math.isfinite(charged) or charged > args.cost_limit:
            raise RuntimeError(f"completed {task} has invalid or over-limit cost; inspect before continuing")
        return "skip"
    if latest.get("status") == "infrastructure_failure" and args.retry_infrastructure:
        return "retry"
    raise RuntimeError(f"prior {task} is not a verified completed trial; inspect {record_path} before retrying")


def run_task(args: argparse.Namespace, task: str, record_path: Path, *, allow_existing: bool = False) -> bool:
    task_root = args.run_root / args.suite / args.configuration / task
    if not allow_existing and task_root.exists() and any(task_root.iterdir()):
        raise FileExistsError(f"prior attempt exists for {args.configuration}/{task}; inspect it before any rerun: {task_root}")
    run_id = f"{task}--context-{args.configuration.lower()}--{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    command = command_for(args, task, run_id, task_root)
    print(" ".join(command), flush=True)
    if not args.live:
        return True

    task_root.mkdir(parents=True, exist_ok=True)
    trial = task_root / run_id
    log_path = task_root / f"{run_id}.launcher.log"
    manifest_path = task_root / f"{run_id}.manifest.json"
    manifest = {
        "suite": args.suite,
        "configuration": args.configuration,
        "task_id": task,
        "model": args.model,
        "command": command,
        "source_commit": source_commit(),
        "tua_commit": tua_commit(args.tua_root),
        "harbor_version": harbor_version(),
        "mini_swe_agent_version": "2.4.3",
        "code_sha256": code_sha256(),
        "code_file_sha256": {str(path.relative_to(ROOT)): sha256_file(path) for path in CODE_FILES},
        "base_config_sha256": sha256_file(BASE_CONFIG),
        "variant_config_sha256": sha256_file(CONFIGS[args.configuration]) if args.configuration != "C0" else "",
        "task_list_sha256": sha256_file(CANONICAL_TASKS),
        "docker_default_platform": os.environ.get("DOCKER_DEFAULT_PLATFORM", ""),
        "cost_limit_usd": args.cost_limit,
        "cost_limit_note": "Harbor/mini-SWE cost gate may see zero; actual usage cost is audited after each task.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    started = time.monotonic()
    returncode = run_with_heartbeat(command, args.tua_root, log_path, args.progress_interval, task)
    elapsed = round(time.monotonic() - started, 2)

    row: dict[str, Any] = {
        "suite": args.suite, "config_id": args.configuration, "task_id": task, "run_id": run_id,
        "wall_time_s": elapsed, "model": args.model, "source_commit": manifest["source_commit"],
        "code_sha256": manifest["code_sha256"], "base_config_sha256": manifest["base_config_sha256"],
        "variant_config_sha256": manifest["variant_config_sha256"], "log_path": str(log_path),
        "trial_path": str(trial), "manifest_path": str(manifest_path),
    }
    result_path = trial / "result.json"
    if not result_path.exists():
        row.update(status="infrastructure_failure", exception="missing_result", cost_status="unknown")
        append_csv(record_path, row)
        return False
    try:
        result = load_json(result_path)
    except (OSError, ValueError) as error:
        row.update(status="infrastructure_failure", exception=f"invalid_result:{type(error).__name__}", cost_status="unknown")
        append_csv(record_path, row)
        return False
    trajectories = list(trial.rglob("mini-swe-agent.trajectory.json"))
    if len(trajectories) == 1:
        row["trajectory_path"] = str(trajectories[0])
        try:
            row.update(trajectory_metrics(trajectories[0]))
        except (OSError, ValueError) as error:
            row.update(cost_status="invalid_trajectory", exception=f"invalid_trajectory:{type(error).__name__}")
    else:
        row["cost_status"] = "missing_or_ambiguous_trajectory"
    row["reward"] = ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward", "")
    exception = result.get("exception_info")
    if exception:
        row["exception"] = exception.get("exception_type", "") if isinstance(exception, dict) else str(exception)
    else:
        row.setdefault("exception", "")
    row["status"] = "completed" if returncode == 0 and not exception and len(trajectories) == 1 and row.get("cost_status") != "invalid_trajectory" else "infrastructure_failure"
    append_csv(record_path, row)
    if row["status"] != "completed" or row.get("cost_status") != "complete":
        print(f"Stopped after {task}: status={row['status']}, cost_status={row.get('cost_status')}. Inspect {log_path}", file=sys.stderr)
        return False
    if float(row["agent_usd"]) > args.cost_limit:
        print(f"Stopped after {task}: actual response cost exceeded the stated per-task cap; see {record_path}", file=sys.stderr)
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", choices=("C0", "A", "B", "AB"), required=True)
    parser.add_argument("--suite", choices=("smoke", "formal"), required=True)
    parser.add_argument("--tua-root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--task-list", type=Path, default=CANONICAL_TASKS)
    parser.add_argument("--cost-limit", type=float, default=0.06)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs/context")
    parser.add_argument("--record-root", type=Path, default=ROOT / "results/context")
    parser.add_argument("--progress-interval", type=float, default=30.0, help="Seconds between terminal status messages during a trial")
    parser.add_argument("--resume", action="store_true", help="Skip completed tasks only when their saved code, settings, cost and trajectory match")
    parser.add_argument("--retry-infrastructure", action="store_true", help="With --resume, preserve a failed trial and make a new attempt")
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--live", action="store_true", help="Actually start Harbor trials; omitted means print commands only")
    args = parser.parse_args()
    args.tua_root = args.tua_root.expanduser().resolve()
    args.run_root = args.run_root.expanduser().resolve()
    args.record_root = args.record_root.expanduser().resolve()
    if args.cost_limit <= 0:
        parser.error("--cost-limit must be positive")
    if not math.isfinite(args.progress_interval) or args.progress_interval < 1:
        parser.error("--progress-interval must be at least 1 second")
    if args.retry_infrastructure and not args.resume:
        parser.error("--retry-infrastructure requires --resume")
    if not args.tua_root.is_dir():
        parser.error("--tua-root does not exist")
    tasks = args.task or read_task_list(args.task_list)
    if len(tasks) != len(set(tasks)):
        parser.error("duplicate --task values")
    if args.suite == "formal" and tasks != read_task_list(CANONICAL_TASKS):
        parser.error("formal suite must use the canonical 40-task list, in order")
    if args.suite == "smoke" and len(tasks) != 1:
        parser.error("smoke suite must have exactly one task")
    args.tasks = tasks
    return args


def main() -> int:
    args = parse_args()
    if args.live and not (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("MSWEA_API_KEY")):
        print("No provider key is set in this terminal. Set it locally; never paste it into chat.", file=sys.stderr)
        return 2
    if args.live and tua_commit(args.tua_root) != EXPECTED_TUA_COMMIT:
        print(f"TUA-Bench checkout must be pinned to {EXPECTED_TUA_COMMIT}.", file=sys.stderr)
        return 2
    if args.live and harbor_version() != "0.6.3":
        print("Harbor must be version 0.6.3 in this Python environment.", file=sys.stderr)
        return 2
    record_path = args.record_root / f"{args.suite}-{args.configuration}.csv"
    durations: list[float] = []
    total = len(args.tasks)
    if args.live:
        print(f"Batch: {total} task(s), configuration {args.configuration}, Docker platform {os.environ.get('DOCKER_DEFAULT_PLATFORM') or 'system default'}.", flush=True)
        print("Each task reports elapsed time every " + duration_text(args.progress_interval) + "; a rough batch ETA appears after the first completed task.", flush=True)
    for index, task in enumerate(args.tasks):
        action = prior_action(args, task, record_path)
        if action == "skip":
            print(f"{progress_text(index + 1, total)} Skipped verified completed {task}; no model call.", flush=True)
            continue
        if args.live:
            print(f"{progress_text(index, total)} Starting {task}" + (" (infrastructure retry)" if action == "retry" else ""), flush=True)
        task_started = time.monotonic()
        if not run_task(args, task, record_path, allow_existing=action == "retry"):
            return 1
        if args.live:
            durations.append(time.monotonic() - task_started)
            remaining = total - index - 1
            eta = duration_text(sum(durations) / len(durations) * remaining)
            print(f"{progress_text(index + 1, total)} Finished {task}; rough remaining time {eta} (task durations vary).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
