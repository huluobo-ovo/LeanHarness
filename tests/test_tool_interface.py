from __future__ import annotations

from copy import deepcopy

import pytest

from leanharness.tools import ToolInterfaceWrapper, guard_result, normalize_result, validate_action


@pytest.mark.parametrize(
    ("action", "category"),
    [({}, "missing_command"), ({"command": 123}, "missing_command"), ({"command": ""}, "empty_command"), ({"command": "   "}, "empty_command")],
)
def test_guard_rejects_missing_or_empty_command(action, category):
    decision = validate_action(action, max_command_chars=10)

    assert decision.should_execute is False
    assert decision.category == category


def test_guard_rejects_too_long_command_and_preserves_tool_call_id():
    action = {"command": "x" * 11, "tool_call_id": "call_123"}
    decision = validate_action(action, max_command_chars=10)

    assert decision.should_execute is False
    assert decision.category == "command_too_long"
    assert decision.action["tool_call_id"] == "call_123"


def test_guard_allows_valid_command_at_length_boundary():
    action = {"command": "x" * 10, "tool_call_id": "call_123"}
    decision = validate_action(action, max_command_chars=10)

    assert decision.should_execute is True
    assert decision.action == action


def test_guard_result_has_environment_shape():
    decision = validate_action({"command": ""}, max_command_chars=10)
    result = guard_result(decision)

    assert result["returncode"] != 0
    assert result["output"] == ""
    assert result["extra"]["leanharness_guarded"] is True
    assert result["extra"]["leanharness_guard_reason"] == "empty_command"


@pytest.mark.parametrize(
    ("result", "category"),
    [
        ({"output": "done", "returncode": 0, "exception_info": ""}, "success"),
        ({"output": "cat: a: No such file or directory", "returncode": 1, "exception_info": ""}, "file_not_found"),
        ({"output": "foo: command not found", "returncode": 127, "exception_info": ""}, "command_not_found"),
        ({"output": "PERMISSION DENIED", "returncode": 1, "exception_info": ""}, "permission_denied"),
        ({"output": "", "returncode": -1, "exception_info": "timed out"}, "timeout_or_exception"),
        ({"output": "unrecognized issue", "returncode": 1, "exception_info": ""}, "other_failure"),
    ],
)
def test_normalizer_classifies_results(result, category):
    normalized = normalize_result(result, summary_max_chars=600, raw_tail_max_chars=3000)

    assert normalized["extra"]["leanharness_category"] == category
    assert normalized["extra"]["leanharness_summary"]
    assert normalized["extra"]["leanharness_next_step"]


def test_normalizer_preserves_original_fields_and_extra_without_mutating_input():
    result = {
        "output": "cat: src/mian.py: No such file or directory",
        "returncode": 1,
        "exception_info": "",
        "extra": {"original": "keep"},
    }
    original = deepcopy(result)

    normalized = normalize_result(result, summary_max_chars=600, raw_tail_max_chars=3000)

    assert result == original
    assert normalized["output"] == original["output"]
    assert normalized["returncode"] == original["returncode"]
    assert normalized["exception_info"] == original["exception_info"]
    assert normalized["extra"]["original"] == "keep"
    assert normalized["extra"]["leanharness_category"] == "file_not_found"


def test_normalizer_limits_raw_tail_without_changing_full_output():
    result = {"output": "prefix-" + "x" * 100, "returncode": 1, "exception_info": ""}
    normalized = normalize_result(result, summary_max_chars=50, raw_tail_max_chars=12)

    assert normalized["output"] == result["output"]
    assert len(normalized["extra"]["leanharness_raw_tail"]) <= 12
    assert normalized["extra"]["leanharness_raw_tail"].endswith("x" * 11)


def test_guarded_result_keeps_its_feedback_after_normalization():
    result = guard_result(validate_action({"command": ""}, max_command_chars=10))
    normalized = normalize_result(result, summary_max_chars=600, raw_tail_max_chars=3000)

    assert normalized["extra"]["leanharness_category"] == "guarded_request"
    assert normalized["extra"]["leanharness_guard_reason"] == "empty_command"
    assert "empty" in normalized["extra"]["leanharness_summary"].lower()


def test_wrapper_executes_valid_action_then_normalizes_result():
    calls = []

    def fake_execute(action):
        calls.append(action)
        return {"output": "done", "returncode": 0, "exception_info": ""}

    wrapper = ToolInterfaceWrapper(fake_execute, guard_enabled=True, normalizer_enabled=True)
    result = wrapper.execute({"command": "echo done", "tool_call_id": "call_ok"})

    assert calls == [{"command": "echo done", "tool_call_id": "call_ok"}]
    assert result["extra"]["leanharness_category"] == "success"


def test_wrapper_does_not_execute_guarded_action():
    calls = []

    def fake_execute(action):
        calls.append(action)
        return {"output": "should not happen", "returncode": 0, "exception_info": ""}

    wrapper = ToolInterfaceWrapper(fake_execute, guard_enabled=True, normalizer_enabled=True)
    result = wrapper.execute({"command": "", "tool_call_id": "call_blocked"})

    assert calls == []
    assert result["extra"]["leanharness_category"] == "guarded_request"


def test_wrapper_with_both_flags_off_returns_baseline_result_unchanged():
    baseline_result = {"output": "raw", "returncode": 1, "exception_info": "", "extra": {"keep": True}}

    wrapper = ToolInterfaceWrapper(lambda action: baseline_result, guard_enabled=False, normalizer_enabled=False)
    result = wrapper.execute({"command": "any command"})

    assert result is baseline_result
