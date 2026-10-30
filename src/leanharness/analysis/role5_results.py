"""Pre-registered Role 5 task-level metric calculations."""

from __future__ import annotations

from collections import defaultdict


CONFIGS = ("C0", "R5-A", "R5-A+B", "R5-B")
EXCLUDED_STATUSES = {"not_run", "infrastructure_failure"}
FAILURE_COUNT_FIELDS = (
    "file_not_found",
    "command_not_found",
    "permission_denied",
    "timeout_or_exception",
    "other_failures",
)
REQUIRED_COLUMNS = {
    "configuration", "task_id", "run_status", "reward", "exception",
    "actual_openrouter_cost_usd", "tool_actions", "guarded_actions",
    "file_not_found", "command_not_found", "permission_denied",
    "timeout_or_exception", "other_failures",
}


def number(row: dict[str, str], field: str, *, blank_as_zero: bool = False) -> float:
    value = (row.get(field) or "").strip()
    if not value and blank_as_zero:
        return 0.0
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"task {row.get('task_id', '<unknown>')}: {field} must be numeric") from error


def latest_evaluable_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep the last valid attempt for each task, preserving CSV order.

    Raw CSVs retain every attempt for auditability. Metrics, however, need one
    observation per task/configuration. A documented infrastructure retry can
    therefore leave an earlier infrastructure row and a later valid row. If a
    valid task was rerun, the last valid row is the one used for metrics.
    Infrastructure-only rows never replace an existing valid observation.
    """
    latest_by_task: dict[str, dict[str, str]] = {}
    for row in rows:
        if (row.get("run_status") or "").strip() not in EXCLUDED_STATUSES:
            latest_by_task[(row.get("task_id") or "").strip()] = row
    return list(latest_by_task.values())


def summarize(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Return one metrics row for each pre-registered C0/R5-A/R5-A+B/R5-B configuration."""
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
        evaluable_attempts = [row for row in all_rows if (row.get("run_status") or "").strip() not in EXCLUDED_STATUSES]
        evaluable = latest_evaluable_rows(all_rows)
        successful = [row for row in evaluable if number(row, "reward") > 0 and row["exception"].strip() == "NO"]
        total_cost = sum(number(row, "actual_openrouter_cost_usd") for row in evaluable)
        total_actions = sum(number(row, "tool_actions") for row in evaluable)
        guarded = sum(number(row, "guarded_actions") for row in evaluable)
        executed_failures = sum(
            number(row, field, blank_as_zero=True)
            for row in evaluable
            for field in FAILURE_COUNT_FIELDS
        )
        summary.append({
            "configuration": config,
            "rows_recorded": len(all_rows),
            "evaluable_attempts": len(evaluable_attempts),
            "evaluable_tasks": len(evaluable),
            "excluded_runs": len(all_rows) - len(evaluable_attempts),
            "superseded_evaluable_attempts": len(evaluable_attempts) - len(evaluable),
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
