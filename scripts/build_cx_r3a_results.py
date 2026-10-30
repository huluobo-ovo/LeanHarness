#!/usr/bin/env python3
"""Build the compact, reviewable CX R3-A result package from local Harbor runs."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = [
    ROOT / "runs/cx-r3-a/cx-r3a-20261030-193259",
    ROOT / "runs/cx-r3-a/cx-r3a-20261030-1948",
]
OUT = ROOT / "results/cx-r3-a"


def upstream_cost(trajectory: Path) -> float:
    if not trajectory.exists():
        return 0.0
    data = json.loads(trajectory.read_text())

    def walk(value):
        if isinstance(value, dict):
            details = value.get("cost_details")
            if isinstance(details, dict) and isinstance(details.get("upstream_inference_cost"), (int, float)):
                yield float(details["upstream_inference_cost"])
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    return sum(walk(data))


def seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()


def main() -> None:
    rows = []
    for run in RUNS:
        for path in sorted(run.glob("*/result.json")):
            result = json.loads(path.read_text())
            task = result["task_name"].split("/", 1)[-1]
            agent = result.get("agent_result") or {}
            reward = (result.get("verifier_result") or {}).get("rewards", {}).get("reward")
            trajectory = path.parent / "agent/mini-swe-agent.trajectory.json"
            rows.append({
                "task_id": task,
                "trial_name": result["trial_name"],
                "reward": reward,
                "exception": "YES" if result.get("exception_info") else "NO",
                "status": "completed" if result.get("finished_at") else "unfinished",
                "runtime_seconds": seconds(result.get("started_at"), result.get("finished_at")),
                "input_tokens": agent.get("n_input_tokens"),
                "cache_tokens": agent.get("n_cache_tokens"),
                "output_tokens": agent.get("n_output_tokens"),
                "harbor_cost_usd": agent.get("cost_usd"),
                "actual_openrouter_cost_usd": upstream_cost(trajectory),
                "trajectory_path": str(trajectory.relative_to(ROOT)),
                "notes": "Harbor cost_usd is 0.0; actual cost is summed from trajectory cost_details.upstream_inference_cost.",
            })

    rows.sort(key=lambda item: item["task_id"])
    assert len(rows) == 40 and len({row["task_id"] for row in rows}) == 40
    assert all(row["status"] == "completed" and row["exception"] == "NO" for row in rows)
    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (OUT / "formal-results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total_reward = sum(float(row["reward"]) for row in rows)
    total_cost = sum(float(row["actual_openrouter_cost_usd"]) for row in rows)
    full = sum(row["reward"] == 1.0 for row in rows)
    zero = sum(row["reward"] == 0.0 for row in rows)
    partial = len(rows) - full - zero
    over_cap = [row for row in rows if float(row["actual_openrouter_cost_usd"]) > 0.10]
    readme = f"""# CX R3-A detect-only formal results\n\n## Result\n\n| Metric | Value |\n| --- | ---: |\n| Tasks | 40 |\n| Mean reward | {total_reward / len(rows):.10f} |\n| Total reward | {total_reward:.10f} |\n| Full / partial / zero reward | {full} / {partial} / {zero} |\n| Harbor exceptions | 0 |\n| Automatic retries | 0 |\n| Actual OpenRouter cost | USD {total_cost:.9f} |\n| Average actual cost per task | USD {total_cost / len(rows):.9f} |\n\n## Fixed setup\n\n- Configuration: CX, R3-A / Failure Recovery detect-only.\n- Agent config: `contributions/yichen-tang/failure_recovery/failure-recovery-ablation.yaml` (`fr_detect=true`, `fr_salvage=false`).\n- Model: `openrouter/particle-ai/particle-1`; mini-SWE-agent 2.4.3; Harbor 0.6.3; Python 3.12.15.\n- Platform/concurrency/limits: linux/amd64, one concurrent task, 30 steps and 900 seconds per task, nominal USD 0.10 agent cost limit.\n- Source jobs: smoke task `000-count-nuclei` in `cx-r3a-20261030-193259`, then the 39-task batch in `cx-r3a-20261030-1948`.\n\n## Cost and provenance note\n\nHarbor wrote `cost_usd=0.0` for every result despite OpenRouter costs being present in the raw agent trajectories. `formal-results.csv` therefore uses the sum of every trajectory response's `cost_details.upstream_inference_cost` as the actual model cost. Two trials exceeded the nominal USD 0.10 limit: {', '.join(f"{row['task_id']} (USD {row['actual_openrouter_cost_usd']:.9f})" for row in over_cap)}. This is a cost-accounting/limit-enforcement observation, not an infrastructure failure.\n\nRaw Harbor artifacts, logs, trajectories, verifier output, and task artifacts remain in the ignored local `runs/cx-r3-a/` directory. They are not committed to keep the repository lean and avoid accidental inclusion of local material.\n\n## Files\n\n- `formal-results.csv`: one final row for each of the 40 tasks.\n- `TEAM_NOTE_CN.md`: concise Chinese handoff message for teammates.\n"""
    (OUT / "README.md").write_text(readme)
    note = f"""# CX R3-A 正式实验结果说明（可转发）\n\n我们完成了 CX 的 R3-A detect-only 正式实验，共 40 题（含 smoke 的第 1 题）。配置为 Particle-1、mini-SWE-agent 2.4.3、Harbor 0.6.3、单并发、每题最多 30 步/900 秒；Failure Recovery 仅开启 detect，未开启 salvage。\n\n结果：平均 reward 为 **{total_reward / len(rows):.4f}**（总 reward {total_reward:.4f}）；{full} 题满分、{partial} 题部分得分、{zero} 题 0 分；Harbor exception 为 0，未发生基础设施失败，也没有自动重跑。\n\n实际 OpenRouter 费用合计 **USD {total_cost:.6f}**，每题平均 USD {total_cost / len(rows):.6f}。注意 Harbor 汇总字段错误显示为 0；这里的费用改为从每题 trajectory 的 OpenRouter 回传 `upstream_inference_cost` 汇总。`054-prostate-label-obj` 和 `033-prostate-volume-est` 分别花费 USD 0.113809458 与 USD 0.111104222，略高于名义 USD 0.10 限额，说明这次运行中费用回传没有被限额机制有效约束。\n\n详细逐题 reward、token、运行时长和真实费用见 `results/cx-r3-a/formal-results.csv`；方法、固定条件与数据来源见同目录 `README.md`。原始日志和 trajectory 保留在本地 `runs/cx-r3-a/`，未上传到 GitHub。\n"""
    (OUT / "TEAM_NOTE_CN.md").write_text(note)


if __name__ == "__main__":
    main()
