#!/usr/bin/env python3
"""Build auditable Role 4 result tables from local Harbor artifacts.

Raw Harbor artifacts stay local under ``results/raw``.  This script selects a
permitted infrastructure rerun only when the original trial has an exception,
then exports the final 40-task tables plus an explicit rerun ledger.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw"
OUT = ROOT / "results" / "role4"
TASK_LIST = ROOT / "configs" / "task_list_40.txt"

CONFIGS = {
    "R4-A": {
        "label": "workflow-only ablation",
        "original": RAW / "role4-ablation-40" / "2026-10-29__01-25-13",
        "rerun": RAW / "role4-ablation-infra-reruns" / "2026-10-29__08-07-08",
        "actual_batch_cost_usd": None,
    },
    "R4-A+B": {
        "label": "workflow + mandatory verification checklist",
        "original": RAW / "role4-main-40" / "2026-10-27__18-23-13",
        "rerun": RAW / "role4-main-infra-reruns" / "2026-10-28__08-29-58",
        "actual_batch_cost_usd": 1.0239,
    },
}

PILOTS = [
    RAW / "role4-pilot-main" / "2026-10-27__16-51-26",
    RAW / "role4-pilot-main-amd64" / "2026-10-27__17-38-40",
    RAW / "role4-pilot-main-amd64-timeout" / "2026-10-27__17-54-28",
]

RAW_ARTIFACT_ROOTS = [
    CONFIGS["R4-A+B"]["original"],
    CONFIGS["R4-A+B"]["rerun"],
    CONFIGS["R4-A"]["original"],
    CONFIGS["R4-A"]["rerun"],
    PILOTS[-1],
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def task_names() -> list[str]:
    return [
        line.strip()
        for line in TASK_LIST.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def load_trials(job_dir: Path) -> dict[str, tuple[Path, dict]]:
    trials: dict[str, tuple[Path, dict]] = {}
    for path in sorted(job_dir.glob("*/result.json")):
        data = read_json(path)
        name = data["task_name"].split("/")[-1]
        if name in trials:
            raise ValueError(f"duplicate task {name} in {job_dir}")
        trials[name] = (path.parent, data)
    return trials


def iso_duration(start: str | None, finish: str | None) -> float | None:
    if not start or not finish:
        return None
    first = datetime.fromisoformat(start.replace("Z", "+00:00"))
    last = datetime.fromisoformat(finish.replace("Z", "+00:00"))
    return round((last - first).total_seconds(), 3)


def local_date(timestamp: str) -> str:
    value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return value.astimezone(ZoneInfo("Asia/Singapore")).date().isoformat()


def repo_path(path: Path) -> str:
    """Return a portable repository-relative artifact path."""
    return path.resolve().relative_to(ROOT).as_posix()


def reward(data: dict) -> float | None:
    return ((data.get("verifier_result") or {}).get("rewards") or {}).get("reward")


def trajectory_details(folder: Path) -> tuple[str, str, str, bool]:
    path = folder / "agent" / "mini-swe-agent.trajectory.json"
    if not path.exists():
        return "", "", "", False
    trajectory = read_json(path)
    info = trajectory.get("info") or {}
    model = ((info.get("config") or {}).get("model") or {}).get("model_name", "")
    version = info.get("mini_version", "")
    exit_status = info.get("exit_status", "")
    submitted = False
    for message in trajectory.get("messages") or []:
        for call in message.get("tool_calls") or []:
            try:
                arguments = json.loads(call.get("function", {}).get("arguments") or "{}")
            except json.JSONDecodeError:
                continue
            if arguments.get("command", "").strip() == "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT":
                submitted = True
    return model, version, exit_status, submitted


def verifier_probe_commands(folder: Path) -> list[str]:
    """Return agent commands that referenced the protected verifier-log path."""
    path = folder / "agent" / "mini-swe-agent.trajectory.json"
    if not path.exists():
        return []
    commands: list[str] = []
    for message in read_json(path).get("messages") or []:
        for call in message.get("tool_calls") or []:
            try:
                arguments = json.loads(call.get("function", {}).get("arguments") or "{}")
            except json.JSONDecodeError:
                continue
            command = arguments.get("command", "")
            if "/logs/verifier" in command:
                commands.append(command)
    return commands


def reason_for(exception: dict | None, trial_dir: Path | None = None) -> str:
    if not exception:
        return ""
    kind = exception.get("exception_type", "")
    message = exception.get("exception_message", "")
    if trial_dir:
        agent_log = trial_dir / "agent" / "mini-swe-agent.txt"
        if agent_log.exists():
            message += "\n" + agent_log.read_text(errors="replace")
    lower = message.lower()
    if "openrouter" in lower and ("name or service not known" in lower or "apiconnectionerror" in lower):
        return "OpenRouter DNS/network failure before a valid agent result"
    if "registry-1.docker.io" in lower or "docker compose command failed" in lower:
        return "Docker image build/pull network failure"
    if kind == "AgentSetupTimeoutError":
        return "Agent dependency setup exceeded the infrastructure timeout"
    if "uv tool install" in lower or "apt-get" in lower:
        return "Agent/container dependency installation failure"
    return f"Infrastructure failure: {kind}"


def note_for(exit_status: str, submitted: bool, source: str) -> str:
    notes: list[str] = []
    if source == "infrastructure_rerun":
        notes.append("permitted replacement for documented infrastructure failure")
    if exit_status == "LimitsExceeded":
        notes.append("30-step limit reached; result retained")
    elif exit_status == "TimeExceeded":
        notes.append("900-second agent wall-time limit reached; result retained")
    if not submitted:
        notes.append("completion command not issued before the enforced limit")
    return "; ".join(notes)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    expected = task_names()
    if len(expected) != 40 or len(set(expected)) != 40:
        raise ValueError("the canonical task list must contain 40 unique tasks")

    final_by_config: dict[str, dict[str, tuple[Path, dict, str]]] = {}
    rerun_rows: list[dict] = []

    for config_id, spec in CONFIGS.items():
        original = load_trials(spec["original"])
        rerun = load_trials(spec["rerun"])
        if set(original) != set(expected):
            raise ValueError(f"{config_id} original task set does not match the canonical list")

        failed = {name for name, (_, data) in original.items() if data.get("exception_info")}
        if set(rerun) != failed:
            raise ValueError(f"{config_id} rerun task set does not exactly match infrastructure failures")

        final: dict[str, tuple[Path, dict, str]] = {}
        for name in expected:
            if name in failed:
                folder, data = rerun[name]
                source = "infrastructure_rerun"
                original_folder, original_data = original[name]
                replacement_exception = data.get("exception_info")
                rerun_rows.append(
                    {
                        "configuration": config_id,
                        "task_id": name,
                        "original_trial": original_folder.name,
                        "original_exception": original_data["exception_info"]["exception_type"],
                        "infrastructure_reason": reason_for(
                            original_data["exception_info"], original_folder
                        ),
                        "replacement_trial": folder.name,
                        "replacement_status": "completed" if not replacement_exception else "exception",
                        "replacement_reward": reward(data),
                        "original_result_path": repo_path(original_folder / "result.json"),
                        "replacement_result_path": repo_path(folder / "result.json"),
                    }
                )
            else:
                folder, data = original[name]
                source = "initial"
            if data.get("exception_info") or not data.get("finished_at"):
                raise ValueError(f"{config_id}/{name} has no valid final result")
            final[name] = (folder, data, source)
        final_by_config[config_id] = final

    formal_rows: list[dict] = []
    summary_rows: list[dict] = []
    compliance_rows: list[dict] = []
    for config_id, spec in CONFIGS.items():
        rewards: list[float] = []
        runtimes: list[float] = []
        tokens = Counter()
        exits = Counter()
        submitted_count = 0
        verifier_probe_tasks = 0

        for name in expected:
            folder, data, source = final_by_config[config_id][name]
            model, version, exit_status, submitted = trajectory_details(folder)
            task_reward = reward(data)
            if task_reward is None:
                raise ValueError(f"missing reward for {config_id}/{name}")
            trial_runtime = iso_duration(data.get("started_at"), data.get("finished_at"))
            execution = data.get("agent_execution") or {}
            runtime = iso_duration(execution.get("started_at"), execution.get("finished_at"))
            agent_result = data.get("agent_result") or {}
            rewards.append(float(task_reward))
            if runtime is not None:
                runtimes.append(runtime)
            tokens["input"] += agent_result.get("n_input_tokens") or 0
            tokens["cache"] += agent_result.get("n_cache_tokens") or 0
            tokens["output"] += agent_result.get("n_output_tokens") or 0
            exits[exit_status] += 1
            submitted_count += int(submitted)
            probes = verifier_probe_commands(folder)
            verifier_probe_tasks += int(bool(probes))
            for command in probes:
                compliance_rows.append(
                    {
                        "configuration": config_id,
                        "task_id": name,
                        "reward": task_reward,
                        "finding": "agent command referenced /logs/verifier",
                        "observed_result": (
                            "directory listing was empty; no verifier file path or content "
                            "was returned in the trajectory"
                        ),
                        "command": command,
                        "trajectory_path": repo_path(
                            folder / "agent" / "mini-swe-agent.trajectory.json"
                        ),
                    }
                )
            formal_rows.append(
                {
                    "run_date": local_date(data["started_at"]),
                    "configuration": config_id,
                    "task_id": name,
                    "model": model or "openrouter/minimax/minimax-m3.1-flash",
                    "agent_version": version or "2.4.3",
                    "run_status": "completed",
                    "reward": task_reward,
                    "exception": "NO",
                    "runtime_seconds": runtime,
                    "trial_runtime_seconds": trial_runtime,
                    "input_tokens": agent_result.get("n_input_tokens") or 0,
                    "cache_tokens": agent_result.get("n_cache_tokens") or 0,
                    "output_tokens": agent_result.get("n_output_tokens") or 0,
                    "harbor_cost_usd": agent_result.get("cost_usd") or 0.0,
                    "actual_openrouter_cost_usd": "",
                    "agent_exit_status": exit_status,
                    "submitted_completion_command": "YES" if submitted else "NO",
                    "source_batch": source,
                    "trial_name": folder.name,
                    "trajectory_path": repo_path(
                        folder / "agent" / "mini-swe-agent.trajectory.json"
                    ),
                    "notes": note_for(exit_status, submitted, source),
                }
            )

        summary_rows.append(
            {
                "configuration": config_id,
                "description": spec["label"],
                "total_tasks": len(rewards),
                "total_reward": round(sum(rewards), 12),
                "mean_reward": round(sum(rewards) / len(rewards), 12),
                "positive_reward_tasks": sum(value > 0 for value in rewards),
                "full_reward_tasks": sum(value == 1 for value in rewards),
                "partial_reward_tasks": sum(0 < value < 1 for value in rewards),
                "zero_reward_tasks": sum(value == 0 for value in rewards),
                "submitted_tasks": submitted_count,
                "step_limit_tasks": exits["LimitsExceeded"],
                "time_limit_tasks": exits["TimeExceeded"],
                "verifier_path_probe_tasks": verifier_probe_tasks,
                "input_tokens": tokens["input"],
                "cache_tokens": tokens["cache"],
                "output_tokens": tokens["output"],
                "average_runtime_seconds": round(sum(runtimes) / len(runtimes), 3),
                "actual_batch_cost_usd": spec["actual_batch_cost_usd"] if spec["actual_batch_cost_usd"] is not None else "",
            }
        )

    comparison_rows: list[dict] = []
    for name in expected:
        full = reward(final_by_config["R4-A+B"][name][1])
        selected = reward(final_by_config["R4-A"][name][1])
        delta = float(selected) - float(full)
        comparison_rows.append(
            {
                "task_id": name,
                "r4_a_plus_b_reward": full,
                "r4_a_reward": selected,
                "r4_a_minus_r4_a_plus_b": round(delta, 12),
                "comparison": "R4-A better" if delta > 0 else "R4-A+B better" if delta < 0 else "equal",
            }
        )

    pilot_rows: list[dict] = []
    for job in PILOTS:
        summary = read_json(job / "result.json")
        trial_paths = list(job.glob("*/result.json"))
        if len(trial_paths) != 1:
            raise ValueError(f"expected one pilot trial in {job}")
        data = read_json(trial_paths[0])
        exception = data.get("exception_info") or {}
        pilot_rows.append(
            {
                "started_at": summary["started_at"],
                "configuration": "R4-A+B",
                "task_id": data["task_name"].split("/")[-1],
                "run_status": "completed" if not exception else "infrastructure_failure",
                "reward": reward(data) if not exception else "",
                "exception": exception.get("exception_type", ""),
                "runtime_seconds": iso_duration(data.get("started_at"), data.get("finished_at")),
                "trial_path": repo_path(trial_paths[0].parent),
                "notes": reason_for(exception, trial_paths[0].parent),
            }
        )

    raw_manifest_rows: list[dict] = []
    for root in RAW_ARTIFACT_ROOTS:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            raw_manifest_rows.append(
                {
                    "path": repo_path(path),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

    write_csv(
        OUT / "formal-results.csv",
        list(formal_rows[0]),
        formal_rows,
    )
    write_csv(OUT / "summary.csv", list(summary_rows[0]), summary_rows)
    write_csv(OUT / "paired-comparison.csv", list(comparison_rows[0]), comparison_rows)
    write_csv(OUT / "infrastructure-reruns.csv", list(rerun_rows[0]), rerun_rows)
    write_csv(OUT / "pilot-results.csv", list(pilot_rows[0]), pilot_rows)
    write_csv(OUT / "compliance-audit.csv", list(compliance_rows[0]), compliance_rows)
    write_csv(
        OUT / "raw-artifact-manifest.csv",
        list(raw_manifest_rows[0]),
        raw_manifest_rows,
    )

    print(f"wrote {len(formal_rows)} final rows")
    print(f"wrote {len(rerun_rows)} infrastructure rerun rows")
    print(f"wrote {len(compliance_rows)} compliance audit rows")
    print(f"wrote {len(raw_manifest_rows)} raw artifact manifest rows")
    for row in summary_rows:
        print(row)


if __name__ == "__main__":
    main()
