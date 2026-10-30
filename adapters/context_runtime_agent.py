"""Independent context-management overlay for mini-SWE-agent 2.4.3.

Harbor installs this single module in the task container.  It changes only the
model-visible representation of tool observations and older history.  Raw
observations remain in the native trajectory's ``extra.raw_output`` field.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, Field

from minisweagent.agents.default import AgentConfig, DefaultAgent


_DIAGNOSTIC = re.compile(r"\b(error|exception|failed|failure|warning|traceback)\b", re.I)


class ContextSettings(BaseModel):
    output_shaping_enabled: bool = False
    history_compaction_enabled: bool = False
    output_char_limit: int = Field(default=3000, ge=512)
    history_keep_recent_groups: int = Field(default=6, ge=1)
    history_batch_groups: int = Field(default=6, ge=1)
    old_observation_char_limit: int = Field(default=320, ge=120)


class ContextAgentConfig(AgentConfig):
    context_management: ContextSettings = Field(default_factory=ContextSettings)


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _bounded_output(raw: str, *, returncode: Any, exception_info: Any, limit: int) -> str:
    """Render a deterministic, bounded view of one long command output."""
    head = raw[: min(900, limit // 3)]
    tail = raw[-min(900, limit // 3) :]
    middle = raw[len(head) : len(raw) - len(tail)]
    diagnostics: list[str] = []
    for line in middle.splitlines():
        candidate = line.strip()
        if candidate and _DIAGNOSTIC.search(candidate) and candidate not in diagnostics:
            diagnostics.append(candidate[:160])
            if len(diagnostics) == 3:
                break
    payload: dict[str, Any] = {
        "returncode": returncode,
        "output_head": head,
        "middle_diagnostics": diagnostics,
        "output_tail": tail,
        "omitted_middle_chars": len(middle),
        "note": "Output abbreviated; use a targeted read or search to inspect omitted content.",
    }
    if exception_info:
        payload["exception_info"] = str(exception_info)[:160]
    rendered = _json_text(payload)
    while len(rendered) > limit:
        if diagnostics:
            diagnostics.pop()
        elif len(head) > 80:
            head = head[: max(80, len(head) - 100)]
            payload["output_head"] = head
        elif len(tail) > 80:
            tail = tail[min(100, len(tail) - 80) :]
            payload["output_tail"] = tail
        elif len(payload.get("exception_info", "")) > 40:
            payload["exception_info"] = payload["exception_info"][:-20]
        else:
            raise ValueError("output_char_limit cannot fit the observation metadata")
        payload["omitted_middle_chars"] = len(raw) - len(head) - len(tail)
        rendered = _json_text(payload)
    return rendered


def shape_observations(messages: list[dict[str, Any]], settings: ContextSettings) -> list[dict[str, Any]]:
    """Change visible tool content only; preserve the formatter's raw evidence."""
    if not settings.output_shaping_enabled:
        return messages
    result: list[dict[str, Any]] = []
    for message in messages:
        raw = str((message.get("extra") or {}).get("raw_output") or "")
        if message.get("role") != "tool" or len(raw) <= settings.output_char_limit:
            result.append(message)
            continue
        changed = dict(message)
        changed["extra"] = dict(message.get("extra") or {})
        changed["content"] = _bounded_output(
            raw,
            returncode=changed["extra"].get("returncode"),
            exception_info=changed["extra"].get("exception_info"),
            limit=settings.output_char_limit,
        )
        changed["extra"].update(
            {
                "context_output_shaped": True,
                "context_raw_chars": len(raw),
                "context_visible_chars": len(changed["content"]),
            }
        )
        result.append(changed)
    return result


def _compact_old_observation(message: dict[str, Any], limit: int) -> str:
    raw = str((message.get("extra") or {}).get("raw_output") or message.get("content") or "")
    payload: dict[str, Any] = {
        "returncode": (message.get("extra") or {}).get("returncode"),
        "older_output_head": raw[:100],
        "older_output_tail": raw[-100:] if len(raw) > 100 else "",
        "original_output_chars": len(raw),
        "note": "Earlier observation shortened for context.",
    }
    rendered = _json_text(payload)
    while len(rendered) > limit:
        if payload["older_output_tail"]:
            payload["older_output_tail"] = payload["older_output_tail"][10:]
        elif payload["older_output_head"]:
            payload["older_output_head"] = payload["older_output_head"][:-10]
        else:
            raise ValueError("old_observation_char_limit cannot fit metadata")
        rendered = _json_text(payload)
    return rendered


def _complete_action_groups(messages: list[dict[str, Any]]) -> list[list[int]]:
    """Find actions whose distinct tool IDs have all received one result."""
    groups: list[list[int]] = []
    for index, message in enumerate(messages):
        calls = message.get("tool_calls") or []
        if message.get("role") != "assistant" or not calls:
            continue
        expected = [call.get("id") for call in calls if isinstance(call, dict)]
        if len(expected) != len(calls) or any(not value for value in expected) or len(set(expected)) != len(expected):
            continue
        observations: list[int] = []
        for next_index in range(index + 1, len(messages)):
            next_message = messages[next_index]
            if next_message.get("role") == "assistant":
                break
            if next_message.get("role") == "tool":
                observations.append(next_index)
        actual = [messages[tool_index].get("tool_call_id") for tool_index in observations]
        if len(actual) == len(expected) and set(actual) == set(expected):
            groups.append(observations)
    return groups


def project_history(messages: list[dict[str, Any]], settings: ContextSettings) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build one request view without mutating the agent's durable history."""
    groups = _complete_action_groups(messages)
    completed_groups = len(groups)
    batch = settings.history_batch_groups
    cutoff = max(0, (completed_groups - settings.history_keep_recent_groups) // batch * batch)
    if not settings.history_compaction_enabled or cutoff == 0:
        return messages, {"folded_groups": 0, "folded_group_indices": [], "folded_observations": 0}

    folded_positions = {position for group in groups[:cutoff] for position in group}
    projected = list(messages)
    changed_positions = 0
    for position in folded_positions:
        copy = dict(messages[position])
        replacement = _compact_old_observation(copy, settings.old_observation_char_limit)
        if len(replacement) < len(str(copy.get("content") or "")):
            copy["content"] = replacement
            projected[position] = copy
            changed_positions += 1
    return projected, {
        "folded_groups": cutoff,
        "folded_group_indices": list(range(1, cutoff + 1)),
        "folded_observations": changed_positions,
    }


class ContextModelProxy:
    """Intercept model request/observation boundaries, leaving agent limits intact."""

    def __init__(self, model: Any, settings: ContextSettings) -> None:
        self._model = model
        self._settings = settings

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        projected, stats = project_history(messages, self._settings)
        response = self._model.query(projected, **kwargs)
        visible_before = [{key: value for key, value in message.items() if key != "extra"} for message in messages]
        visible_after = [{key: value for key, value in message.items() if key != "extra"} for message in projected]
        shaped = [message for message in messages if (message.get("extra") or {}).get("context_output_shaped")]
        request_text = _json_text(visible_after)
        response.setdefault("extra", {})["context_history"] = {
            **stats,
            "shaped_observations": len(shaped),
            "shaped_raw_chars": sum(int(message["extra"]["context_raw_chars"]) for message in shaped),
            "shaped_visible_chars": sum(int(message["extra"]["context_visible_chars"]) for message in shaped),
            "request_chars_before": len(_json_text(visible_before)),
            "request_chars_after": len(request_text),
            "request_sha256": hashlib.sha256(request_text.encode()).hexdigest(),
            "settings_sha256": hashlib.sha256(_json_text(self._settings.model_dump()).encode()).hexdigest(),
        }
        return response

    def format_observation_messages(
        self, message: dict[str, Any], outputs: list[dict[str, Any]], template_vars: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        rendered = self._model.format_observation_messages(message, outputs, template_vars)
        return shape_observations(rendered, self._settings)


class ContextDefaultAgent(DefaultAgent):
    """The upstream agent with an optional model boundary proxy."""

    def __init__(self, model: Any, env: Any, **kwargs: Any) -> None:
        super().__init__(model, env, config_class=ContextAgentConfig, **kwargs)
        self.model = ContextModelProxy(self.model, self.config.context_management)
