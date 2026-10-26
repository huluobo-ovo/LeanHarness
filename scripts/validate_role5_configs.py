"""Validate the fixed invariants of Role 5's T1/T2 experiment metadata."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "T1": ROOT / "configs" / "tool-interface-normalizer.yaml",
    "T2": ROOT / "configs" / "tool-interface-complete.yaml",
}
EXPECTED_SHARED = {
    "task_list: configs/task_list_40.txt",
    "max_steps: 30",
    "wall_time_limit_seconds: 900",
    "per_task_usd_cap: 0.06",
    "provider: openrouter",
    "name: TEAM_DECISION_REQUIRED",
    "normalizer_enabled: true",
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

    assert "guard_enabled: false" in lines["T1"], "T1 must isolate the normalizer"
    assert "guard_enabled: true" in lines["T2"], "T2 must enable the complete interface"
    print("Role 5 T1/T2 configuration invariants: OK")


if __name__ == "__main__":
    main()
