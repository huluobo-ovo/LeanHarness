from __future__ import annotations

import pytest

from leanharness.analysis.role5_results import summarize


def row(config: str, **overrides: str) -> dict[str, str]:
    base = {
        "configuration": config,
        "task_id": f"task-{config}",
        "run_status": "completed",
        "reward": "0",
        "exception": "NO",
        "actual_openrouter_cost_usd": "0.06",
        "tool_actions": "10",
        "guarded_actions": "0",
        "file_not_found": "1",
        "command_not_found": "1",
        "permission_denied": "0",
        "timeout_or_exception": "0",
        "other_failures": "0",
    }
    return {**base, **overrides}


def test_summary_uses_preregistered_definitions():
    output = summarize(
        [
            row("C0", reward="1"),
            row("R5-A", reward="0"),
            row("R5-A+B", reward="1", guarded_actions="2", file_not_found="0", command_not_found="0"),
            row("R5-B"),
        ]
    )
    by_config = {item["configuration"]: item for item in output}
    c0, t1, t2 = by_config["C0"], by_config["R5-A"], by_config["R5-A+B"]

    assert c0["success_rate"] == 1
    assert c0["mean_actual_cost_per_task_usd"] == 0.06
    assert c0["cost_per_success_usd"] == 0.06
    assert c0["unproductive_executed_action_rate"] == 0.2
    assert t1["cost_per_success_usd"] == ""
    assert t2["unproductive_executed_action_rate"] == 0
    assert t2["guard_intervention_rate"] == 0.2


def test_infrastructure_failure_is_recorded_but_excluded():
    output = summarize([row("C0", run_status="infrastructure_failure"), row("R5-A"), row("R5-A+B"), row("R5-B")])

    assert output[0]["rows_recorded"] == 1
    assert output[0]["evaluable_tasks"] == 0
    assert output[0]["excluded_runs"] == 1


def test_blank_failure_counts_are_zero():
    output = summarize(
        [
            row(
                "C0",
                file_not_found="",
                command_not_found="",
                permission_denied="",
                timeout_or_exception="",
                other_failures="",
            ),
            row("R5-A"),
            row("R5-A+B"),
            row("R5-B"),
        ]
    )

    assert output[0]["executed_failure_actions"] == 0
    assert output[0]["unproductive_executed_action_rate"] == 0


def test_latest_valid_attempt_is_used_for_a_documented_rerun():
    output = summarize(
        [
            row("C0", task_id="054-prostate-label-obj", reward="0", actual_openrouter_cost_usd="0.99"),
            row("C0", task_id="054-prostate-label-obj", reward="1", actual_openrouter_cost_usd="0.05"),
            row("R5-A"),
            row("R5-A+B"),
            row("R5-B"),
        ]
    )

    assert output[0]["rows_recorded"] == 2
    assert output[0]["evaluable_attempts"] == 2
    assert output[0]["evaluable_tasks"] == 1
    assert output[0]["superseded_evaluable_attempts"] == 1
    assert output[0]["successful_tasks"] == 1
    assert output[0]["total_actual_openrouter_cost_usd"] == 0.05


def test_infrastructure_failure_never_replaces_a_valid_result():
    output = summarize(
        [
            row("C0", task_id="033-prostate-volume-est", reward="1"),
            row("C0", task_id="033-prostate-volume-est", run_status="infrastructure_failure", exception="YES"),
            row("R5-A"),
            row("R5-A+B"),
            row("R5-B"),
        ]
    )

    assert output[0]["evaluable_tasks"] == 1
    assert output[0]["excluded_runs"] == 1
    assert output[0]["successful_tasks"] == 1


def test_invalid_exception_is_rejected():
    with pytest.raises(ValueError, match="exception"):
        summarize([row("C0", exception="maybe")])
