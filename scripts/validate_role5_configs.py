"""Validate the fixed invariants of Role 5's R5-A/R5-A+B/R5-B experiment metadata."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "R5-A": ROOT / "configs" / "tool-interface-normalizer.yaml",
    "R5-A+B": ROOT / "configs" / "tool-interface-complete.yaml",
    "R5-B": ROOT / "configs" / "tool-interface-command-guard.yaml",
}
EXPECTED_SHARED = {
    "task_list: configs/task_list_40.txt",
    "max_steps: 30",
    "wall_time_limit_seconds: 900",
    "per_task_usd_cap: 0.06",
    "provider: openrouter",
    "name: TEAM_DECISION_REQUIRED",
    "max_command_chars: 12000",
    "summary_max_chars: 600",
    "raw_tail_max_chars: 3000",
}


def config_lines(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")}


def main() -> None:
    task_ids = [
        line.strip()
        for line in (ROOT / "configs" / "task_list_40.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(task_ids) == 40, f"expected 40 tasks, got {len(task_ids)}"
    assert len(task_ids) == len(set(task_ids)), "task list contains duplicate IDs"

    lines = {name: config_lines(path) for name, path in CONFIGS.items()}
    for name, values in lines.items():
        missing = EXPECTED_SHARED - values
        assert not missing, f"{name} is missing shared fields: {sorted(missing)}"

    assert "guard_enabled: false" in lines["R5-A"], "R5-A must isolate the normalizer"
    assert "normalizer_enabled: true" in lines["R5-A"], "R5-A must enable the normalizer"
    assert "guard_enabled: true" in lines["R5-A+B"], "R5-A+B must enable the complete interface"
    assert "normalizer_enabled: true" in lines["R5-A+B"], "R5-A+B must enable the normalizer"
    assert "guard_enabled: true" in lines["R5-B"], "R5-B must enable the guard"
    assert "normalizer_enabled: false" in lines["R5-B"], "R5-B must isolate the guard"
    print("Role 5 R5-A/R5-A+B/R5-B configuration invariants: OK")


if __name__ == "__main__":
    main()
