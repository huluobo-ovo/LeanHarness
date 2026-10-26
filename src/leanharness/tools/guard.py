"""Pre-execution validation for the baseline ``bash(command)`` tool.

This module deliberately checks only malformed requests. It is not a safety
policy and does not attempt to judge whether a valid shell command is useful.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuardDecision:
    """The outcome of validating one parsed tool action."""

    should_execute: bool
    action: dict[str, Any]
    category: str | None = None
    summary: str | None = None
    next_step: str | None = None


def validate_action(action: dict[str, Any], *, max_command_chars: int) -> GuardDecision:
    """Allow a well-formed action or return a bounded, explainable rejection.

    The parser in mini-SWE-agent already checks JSON syntax and the default
    ``bash`` tool name. This guard performs only semantic checks that are safe
    to make without task-specific knowledge.
    """
    command = action.get("command")
    if not isinstance(command, str):
        return GuardDecision(
            should_execute=False,
            action=action,
            category="missing_command",
            summary="The bash request has no string command argument.",
            next_step="Provide one concrete shell command.",
        )
    if not command.strip():
        return GuardDecision(
            should_execute=False,
            action=action,
            category="empty_command",
            summary="The bash command is empty, so nothing was executed.",
            next_step="Provide one concrete shell command.",
        )
    if len(command) > max_command_chars:
        return GuardDecision(
            should_execute=False,
            action=action,
            category="command_too_long",
            summary="The command exceeds the configured length limit and was not executed.",
            next_step="Split the work into smaller commands.",
        )
    return GuardDecision(should_execute=True, action=action)


def guard_result(decision: GuardDecision) -> dict[str, Any]:
    """Convert a rejected decision into an environment-compatible result.

    The result intentionally has the same top-level fields as a regular
    mini-SWE-agent environment result. This lets the standard observation
    formatter render it and retain tool-call correlation from the action.
    """
    if decision.should_execute:
        raise ValueError("Cannot create a guard result for an executable action")
    return {
        "output": "",
        "returncode": 2,
        "exception_info": "LeanHarness rejected a malformed tool request before execution.",
        "extra": {
            "leanharness_guarded": True,
            "leanharness_guard_reason": decision.category,
            "leanharness_category": "guarded_request",
            "leanharness_summary": decision.summary,
            "leanharness_next_step": decision.next_step,
        },
    }
