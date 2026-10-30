#!/usr/bin/env python3
"""Export small, shareable evidence for group failure analysis.

The source Harbor runs are intentionally ignored because they include hundreds
of megabytes of container artefacts.  This exporter reads them locally and
commits only task-level outcomes plus short command/output evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "failure-analysis"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def redact(text: object) -> str:
    """Remove credentials and machine-specific paths before writing evidence."""
    value = str(text or "")
    value = re.sub(r"(?i)(openrouter_api_key|api[_-]?key)=[^\s'\"]+", r"\1=<REDACTED>", value)
    value = re.sub(r"\bsk-(?:or-v1-)?[A-Za-z0-9_-]{16,}\b", "<REDACTED_API_KEY>", value)
    value = re.sub(r"/Users/[^\s,'\"]+", "<LOCAL_PATH>", value)
    return value


def compact(text: object, limit: int = 480) -> str:
    value = re.sub(r"\s+", " ", redact(text)).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def trajectory_evidence(relative_path: str) -> tuple[list[dict[str, object]], list[str], int]:
    """Return bounded command evidence, automatic signals, and action count."""
    path = ROOT / relative_path
    if not path.exists():
        return [], ["trajectory_not_available_in_package"], 0
    try:
        messages = json.loads(path.read_text()).get("messages", [])
    except (json.JSONDecodeError, OSError):
        return [], ["trajectory_unreadable"], 0

    commands: list[dict[str, object]] = []
    pending: dict[str, str] = {}
    signals: set[str] = set()
    for message in messages:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                try:
                    command = json.loads(function.get("arguments") or "{}").get("command", "")
                except json.JSONDecodeError:
                    command = function.get("arguments", "")
                if command:
                    pending[call.get("id", "")] = str(command)
        elif message.get("role") == "tool":
            raw = (message.get("extra") or {}).get("raw_output", message.get("content", ""))
            return_code = (message.get("extra") or {}).get("returncode")
            command = pending.get(message.get("tool_call_id", ""), "")
            entry = {
                "command": compact(command, 360),
                "return_code": return_code,
                "output_excerpt": compact(raw),
            }
            commands.append(entry)
            lowered = f"{command}\n{raw}".lower()
            if return_code not in (None, 0):
                signals.add("nonzero_command_exit")
            if "not found" in lowered or "no such file" in lowered:
                signals.add("missing_command_or_file")
            if "permission denied" in lowered:
                signals.add("permission_denied")
            if "timed out" in lowered or "timeout" in lowered:
                signals.add("timeout_signal")

    normalized = [item["command"] for item in commands if item["command"]]
    if any(count >= 3 for count in Counter(normalized).values()):
        signals.add("repeated_command")
    # Preserve failures and final context, while keeping the committed file small.
    bad = [item for item in commands if item["return_code"] not in (None, 0)]
    selected = bad[-6:] + commands[-8:]
    seen: set[str] = set()
    deduplicated = []
    for item in selected:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduplicated.append(item)
    return deduplicated, sorted(signals) or ["no_automatic_signal"], len(commands)


def canonical_role5_rows() -> list[dict[str, str]]:
    """One valid final observation per task/config; retain infra-only observations."""
    rows = read_csv(ROOT / "results/role5/formal-results.csv")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["configuration"], row["task_id"]), []).append(row)
    selected: list[dict[str, str]] = []
    for attempts in grouped.values():
        completed = [row for row in attempts if row["run_status"] == "completed"]
        selected.append(completed[-1] if completed else attempts[-1])
    return selected


def add_candidate(
    candidates: list[dict[str, object]], evidence: list[dict[str, object]], *,
    source: str, configuration: str, task_id: str, run_status: str,
    reward: float | None, exception: str, runtime: str, cost: str,
    trajectory_path: str, notes: str,
) -> None:
    local_trajectory = bool(trajectory_path and (ROOT / trajectory_path).exists())
    commands, signals, action_count = trajectory_evidence(trajectory_path) if local_trajectory else ([], ["no_local_trajectory"], 0)
    candidate_id = f"{source}:{configuration}:{task_id}"
    classification = "infrastructure_failure" if run_status == "infrastructure_failure" else "needs_manual_review"
    candidates.append({
        "candidate_id": candidate_id,
        "source": source,
        "configuration": configuration,
        "task_id": task_id,
        "run_status": run_status,
        "reward": "" if reward is None else reward,
        "exception": exception,
        "runtime_seconds": runtime,
        "actual_openrouter_cost_usd": cost,
        "trajectory_available_locally": "yes" if local_trajectory else "no",
        "raw_trajectory_sha256": hashlib.sha256((ROOT / trajectory_path).read_bytes()).hexdigest() if local_trajectory else "",
        "automatic_signals": ";".join(signals),
        "command_action_count": action_count,
        "initial_failure_class": classification,
        "reviewer_failure_class": "",
        "reviewer_evidence": "",
        "reviewer_notes": "",
        "notes": compact(notes, 600),
    })
    evidence.append({
        "candidate_id": candidate_id,
        "source": source,
        "configuration": configuration,
        "task_id": task_id,
        "automatic_signals": signals,
        "command_action_count": action_count,
        "command_evidence": commands,
    })


def main() -> None:
    candidates: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []

    for row in canonical_role5_rows():
        reward = number(row["reward"])
        # Full-score completed trials are not failure-analysis candidates.
        if row["run_status"] == "completed" and reward == 1.0:
            continue
        add_candidate(
            candidates, evidence, source="R5", configuration=row["configuration"],
            task_id=row["task_id"], run_status=row["run_status"], reward=reward,
            exception=row["exception"], runtime=row["runtime_seconds"],
            cost=row["actual_openrouter_cost_usd"], trajectory_path=row["trajectory_path"],
            notes=row["notes"],
        )

    for row in read_csv(ROOT / "results/cx-r3-a/formal-results.csv"):
        reward = number(row["reward"])
        if row["status"] == "completed" and reward == 1.0:
            continue
        add_candidate(
            candidates, evidence, source="CX", configuration="R3-A", task_id=row["task_id"],
            run_status=row["status"], reward=reward, exception=row["exception"],
            runtime=row["runtime_seconds"], cost=row["actual_openrouter_cost_usd"],
            trajectory_path=row["trajectory_path"], notes=row["notes"],
        )

    candidates.sort(key=lambda row: (str(row["source"]), str(row["configuration"]), str(row["task_id"])))
    evidence.sort(key=lambda row: row["candidate_id"])
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "failure-candidates.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(candidates[0]))
        writer.writeheader()
        writer.writerows(candidates)
    with (OUT / "trajectory-evidence.jsonl").open("w") as handle:
        for item in evidence:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    with (OUT / "manual-label-template.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "candidate_id", "reviewer", "primary_failure_class", "secondary_failure_class",
            "evidence_summary", "actionable_fix", "confidence", "notes",
        ])
        writer.writeheader()
        for row in candidates:
            writer.writerow({"candidate_id": row["candidate_id"]})
    role5_count = sum(row["source"] == "R5" for row in candidates)
    cx_count = sum(row["source"] == "CX" for row in candidates)
    readme = f"""# Failure-analysis package

This package is the lightweight, GitHub-shareable counterpart of local Harbor
run artefacts. It contains **{len(candidates)} candidates**: {role5_count} from
Role 5 (R5-A, R5-A+B, R5-B) and {cx_count} from CX/R3-A. A candidate is a
non-full-score completed run or an infrastructure-only run. Full-score runs are
excluded to keep review focused.

## Files

- `failure-candidates.csv` — the assignment sheet. Each row has outcome,
  cost/runtime, automatically detected signals, and empty reviewer fields.
- `trajectory-evidence.jsonl` — bounded command/output excerpts for each row;
  this is evidence, not a model-generated diagnosis.
- `manual-label-template.csv` — a clean sheet for reviewers to divide work.

## Recommended labels

Use one primary label per candidate: `task_misunderstanding`,
`wrong_or_incomplete_artifact`, `tool_or_command_error`, `repeated_ineffective_action`,
`timeout_or_step_limit`, `submission_or_verification_miss`, or
`infrastructure_failure`. Use `unclear` only if the bounded evidence cannot
support a decision. Put the decisive command/output in `evidence_summary`.

## Important interpretation rules

1. `automatic_signals` only searches the recorded command/output text. It is a
   triage aid, not proof of the failure cause.
2. Infrastructure-only Role 5 rows are retained but must not be counted as
   model failures or used in success-rate denominators.
3. Paths and raw artefacts are deliberately omitted. The original trajectories
   remain on the experiment machine under ignored `runs/`; the SHA-256 in the
   CSV lets the owner confirm that a reviewed local trajectory is the same one.
4. This package covers locally available R5 and CX trajectories. For C0/C1/R3/R4,
   use their tracked result files under `results/`; their raw traces were not
   present on this machine, so this exporter does not fabricate evidence.
"""
    (OUT / "README.md").write_text(readme)
    print(f"wrote {len(candidates)} candidates to {OUT}")


if __name__ == "__main__":
    main()
