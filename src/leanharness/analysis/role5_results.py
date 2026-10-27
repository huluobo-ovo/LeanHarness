"""Pre-registered Role 5 task-level metric calculations."""

from __future__ import annotations

from collections import defaultdict


CONFIGS = ("C0", "T1", "T2")
EXCLUDED_STATUSES = {"not_run", "infrastructure_failure"}
REQUIRED_COLUMNS = {
    "configuration", "task_id", "run_status", "reward", "exception",
    "actual_openrouter_cost_usd", "tool_actions", "guarded_actions",
    "file_not_found", "command_not_found", "permission_denied",
    "timeout_or_exception", "other_failures",
}


def number(row: dict[str, str], field: str) -> float:
    try:
        return float((row.get(field) or "").strip())
    except ValueError as error:
        raise ValueError(f"task {row.get('task_id', '<unknown>')}: {field} must be numeric") from error


def summarize(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Return one metrics row for each pre-registered C0/T1/T2 configuration."""
    missing = REQUIRED_COLUMNS - set(rows[0]) if rows else REQUIRED_COLUMNS
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        config = (row.get("configuration") or "").strip()
        if config not in CONFIGS:
            raise ValueError(f"task {row.get('task_id', '<unknown>')}: configuration must be one of {CONFIGS}")
        if (row.get("exception") or "").strip() not in {"YES", "NO"}:
            raise ValueError(f"task {row.get('task_id', '<unknown>')}: exception must be YES or NO")
        grouped[config].append(row)

    summary: list[dict[str, object]] = []
    for config in CONFIGS:
        all_rows = grouped[config]
        evaluable = [row for row in all_rows if (row.get("run_status") or "").strip() not in EXCLUDED_STATUSES]
        successful = [row for row in evaluable if number(row, "reward") > 0 and row["exception"].strip() == "NO"]
        total_cost = sum(number(row, "actual_openrouter_cost_usd") for row in evaluable)
        total_actions = sum(number(row, "tool_actions") for row in evaluable)
        guarded = sum(number(row, "guarded_actions") for row in evaluable)
        executed_failures = sum(number(row, field) for row in evaluable for field in ("file_not_found", "command_not_found", "permission_denied", "timeout_or_exception", "other_failures"))
        summary.append({
            "configuration": config,
            "rows_recorded": len(all_rows),
            "evaluable_tasks": len(evaluable),
            "excluded_runs": len(all_rows) - len(evaluable),
            "successful_tasks": len(successful),
            "success_rate": len(successful) / len(evaluable) if evaluable else "",
            "total_actual_openrouter_cost_usd": total_cost,
            "mean_actual_cost_per_task_usd": total_cost / len(evaluable) if evaluable else "",
            "cost_per_success_usd": total_cost / len(successful) if successful else "",
            "total_tool_actions": total_actions,
            "executed_failure_actions": executed_failures,
            "unproductive_executed_action_rate": executed_failures / total_actions if total_actions else "",
            "guarded_actions": guarded,
            "guard_intervention_rate": guarded / total_actions if total_actions else "",
        })
    return summary
