"""Deterministic post-execution feedback for shell command outcomes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "file_not_found",
        "no such file or directory",
        "The referenced path does not exist.",
        "List or search the directory before retrying that path.",
    ),
    (
        "command_not_found",
        "command not found",
        "The requested command is unavailable or misspelled.",
        "Check the command name or use an installed alternative.",
    ),
    (
        "permission_denied",
        "permission denied",
        "The command lacks permission for the target.",
        "Inspect permissions and the target path before retrying.",
    ),
)


def _limit(value: str, limit: int) -> str:
    if limit < 1:
        return ""
    if len(value) <= limit:
        return value
    if limit == 1:
        return "…"
    return value[: limit - 1] + "…"


def _tail(value: str, limit: int) -> str:
    if limit < 1:
        return ""
    if len(value) <= limit:
        return value
    if limit == 1:
        return "…"
    return "…" + value[-(limit - 1) :]


def _classify(result: dict[str, Any]) -> tuple[str, str, str]:
    extra = result.get("extra") or {}
    if extra.get("leanharness_guarded"):
        return (
            "guarded_request",
            str(extra.get("leanharness_summary") or "A malformed tool request was not executed."),
            str(extra.get("leanharness_next_step") or "Provide one concrete shell command."),
        )

    exception_info = str(result.get("exception_info") or "")
    if exception_info:
        return (
            "timeout_or_exception",
            "The command could not complete because the execution layer reported an exception or timeout.",
            "Try a smaller, bounded command and inspect the error details.",
        )

    returncode = result.get("returncode")
    if returncode == 0:
        return "success", "Command completed with exit code 0.", "Inspect output and continue with the task."

    output = str(result.get("output") or "").casefold()
    for category, marker, summary, next_step in _RULES:
        if marker in output:
            return category, summary, next_step
    return (
        "other_failure",
        "Command failed with a non-zero exit code.",
        "Read the key error lines and choose a different diagnostic or repair step.",
    )


def normalize_result(
    result: dict[str, Any], *, summary_max_chars: int, raw_tail_max_chars: int
) -> dict[str, Any]:
    """Return a copy of *result* enriched with LeanHarness feedback fields.

    No original top-level field or existing ``extra`` field is overwritten.
    The full output remains in ``output``; the bounded raw tail is only a
    convenience for concise observation rendering.
    """
    enriched = deepcopy(result)
    original_extra = enriched.get("extra")
    extra = dict(original_extra) if isinstance(original_extra, dict) else {}
    category, summary, next_step = _classify(enriched)
    output = str(enriched.get("output") or "")

    extra.update(
        {
            "leanharness_category": category,
            "leanharness_summary": _limit(summary, summary_max_chars),
            "leanharness_next_step": _limit(next_step, summary_max_chars),
            "leanharness_raw_tail": _tail(output, raw_tail_max_chars),
        }
    )
    enriched["extra"] = extra
    return enriched
