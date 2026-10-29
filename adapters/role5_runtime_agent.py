"""Runtime overlay installed inside the mini-SWE-agent tool environment.

This file is deliberately dependency-free apart from mini-SWE-agent and
Pydantic.  The Harbor integration script embeds this source into the task
container; it is not imported from the host checkout at run time.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import Field

from minisweagent.agents.default import AgentConfig, DefaultAgent


class Role5AgentConfig(AgentConfig):
    """Accept the Role 5 block while retaining all upstream agent settings."""

    tool_interface: dict[str, Any] = Field(default_factory=dict)


class Role5DefaultAgent(DefaultAgent):
    """Default agent with optional guard and deterministic result feedback."""

    def __init__(self, model: Any, env: Any, **kwargs: Any) -> None:
        super().__init__(model, env, config_class=Role5AgentConfig, **kwargs)

    def execute_actions(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        settings = self.config.tool_interface
        outputs = [self._execute_with_tool_interface(action, settings) for action in message.get("extra", {}).get("actions", [])]
        return self.add_messages(*self.model.format_observation_messages(message, outputs, self.get_template_vars()))

    def _execute_with_tool_interface(self, action: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
        if settings.get("guard_enabled"):
            rejection = _guard(action, int(settings.get("max_command_chars", 12000)))
            if rejection is not None:
                result = rejection
            else:
                result = self.env.execute(action)
        else:
            result = self.env.execute(action)

        if settings.get("normalizer_enabled"):
            return _normalize(
                result,
                summary_max_chars=int(settings.get("summary_max_chars", 600)),
                raw_tail_max_chars=int(settings.get("raw_tail_max_chars", 3000)),
            )
        return result


def _guard(action: dict[str, Any], max_chars: int) -> dict[str, Any] | None:
    command = action.get("command")
    if not isinstance(command, str):
        reason, summary, next_step = "missing_command", "The bash request has no string command argument.", "Provide one concrete shell command."
    elif not command.strip():
        reason, summary, next_step = "empty_command", "The bash command is empty, so nothing was executed.", "Provide one concrete shell command."
    elif len(command) > max_chars:
        reason, summary, next_step = "command_too_long", "The command exceeds the configured length limit and was not executed.", "Split the work into smaller commands."
    else:
        return None
    return {
        "output": "",
        "returncode": 2,
        "exception_info": "LeanHarness rejected a malformed tool request before execution.",
        "extra": {
            "leanharness_guarded": True,
            "leanharness_guard_reason": reason,
            "leanharness_category": "guarded_request",
            "leanharness_summary": summary,
            "leanharness_next_step": next_step,
        },
    }


def _normalize(result: dict[str, Any], *, summary_max_chars: int, raw_tail_max_chars: int) -> dict[str, Any]:
    enriched = deepcopy(result)
    extra = dict(enriched.get("extra") or {})
    if extra.get("leanharness_guarded"):
        category = "guarded_request"
        summary = str(extra.get("leanharness_summary") or "A malformed tool request was not executed.")
        next_step = str(extra.get("leanharness_next_step") or "Provide one concrete shell command.")
    elif enriched.get("exception_info"):
        category = "timeout_or_exception"
        summary = "The command could not complete because the execution layer reported an exception or timeout."
        next_step = "Try a smaller, bounded command and inspect the error details."
    elif enriched.get("returncode") == 0:
        category = "success"
        summary = "Command completed with exit code 0."
        next_step = "Inspect output and continue with the task."
    else:
        output = str(enriched.get("output") or "").casefold()
        categories = (
            ("no such file or directory", "file_not_found", "The referenced path does not exist.", "List or search the directory before retrying that path."),
            ("command not found", "command_not_found", "The requested command is unavailable or misspelled.", "Check the command name or use an installed alternative."),
            ("permission denied", "permission_denied", "The command lacks permission for the target.", "Inspect permissions and the target path before retrying."),
        )
        _, category, summary, next_step = next((item for item in categories if item[0] in output), ("", "other_failure", "Command failed with a non-zero exit code.", "Read the key error lines and choose a different diagnostic or repair step."))
    raw_output = str(enriched.get("output") or "")
    extra.update({
        "leanharness_category": category,
        "leanharness_summary": summary[:summary_max_chars],
        "leanharness_next_step": next_step[:summary_max_chars],
        "leanharness_raw_tail": raw_output[-raw_tail_max_chars:] if raw_tail_max_chars > 0 else "",
    })
    enriched["extra"] = extra
    return enriched
