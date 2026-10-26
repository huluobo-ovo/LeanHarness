"""A thin executor wrapper that composes the v1 guard and normalizer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .guard import guard_result, validate_action
from .normalizer import normalize_result

Executor = Callable[[dict[str, Any]], dict[str, Any]]


class ToolInterfaceWrapper:
    """Apply optional LeanHarness layers without changing the executor contract."""

    def __init__(
        self,
        execute: Executor,
        *,
        guard_enabled: bool = False,
        normalizer_enabled: bool = False,
        max_command_chars: int = 12_000,
        summary_max_chars: int = 600,
        raw_tail_max_chars: int = 3_000,
    ) -> None:
        self._execute = execute
        self.guard_enabled = guard_enabled
        self.normalizer_enabled = normalizer_enabled
        self.max_command_chars = max_command_chars
        self.summary_max_chars = summary_max_chars
        self.raw_tail_max_chars = raw_tail_max_chars

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute an action or synthesize a guarded result, then optionally normalize."""
        if self.guard_enabled:
            decision = validate_action(action, max_command_chars=self.max_command_chars)
            result = self._execute(decision.action) if decision.should_execute else guard_result(decision)
        else:
            result = self._execute(action)

        if self.normalizer_enabled:
            return normalize_result(
                result,
                summary_max_chars=self.summary_max_chars,
                raw_tail_max_chars=self.raw_tail_max_chars,
            )
        return result
