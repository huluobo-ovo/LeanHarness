#!/usr/bin/env python3
"""Export a Harbor job folder to rows for the group data sheet (逐题数据).

Cost per task is the sum of usage.cost from OpenRouter in the trajectory, since
Harbor reports 0.0 for OpenRouter.

python export_rows.py JOB_DIR --member 3号 --config 乙-主 --commit <sha> --harness-zero --xlsx sheet.xlsx
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

COLUMNS = [
    "提交同学", "方案/配置名称", "模型名称", "题目ID", "Run ID", "成功(1/0)", "运行步数", "耗时(秒)",
    "Agent输入Token", "Agent输出Token", "Harness输入Token", "Harness输出Token",
    "Agent实际成本($)", "Harness实际成本($)", "总成本($)(自动)", "结束原因/失败原因",
    "代码Commit", "日志文件名/位置", "备注",
]


def _secs(block: dict | None) -> float | None:
    if not block or not block.get("started_at") or not block.get("finished_at"):
        return None
    f = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    return round((f(block["finished_at"]) - f(block["started_at"])).total_seconds(), 1)


def trial_row(trial: Path, args) -> dict:
    res = json.loads((trial / "result.json").read_text())
    traj_p = trial / "agent" / "mini-swe-agent.trajectory.json"
    traj = json.loads(traj_p.read_text()) if traj_p.exists() else {}
    info = traj.get("info", {})
    msgs = traj.get("messages", [])

    cost = None
    n_in = n_out = n_cache = 0
    for m in msgs:
        usage = ((m.get("extra") or {}).get("response") or {}).get("usage") or {}
        if usage:
            n_in += usage.get("prompt_tokens") or 0
            n_out += usage.get("completion_tokens") or 0
            n_cache += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
            if usage.get("cost") is not None:
                cost = (cost or 0.0) + usage["cost"]

    rewards = (res.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward")
    exc = res.get("exception_info")
    exit_status = info.get("exit_status", "")
    reason = exit_status or ""
    if exc:
        reason = (reason + "; " if reason else "") + f"Exception: {exc.get('exception_type', exc) if isinstance(exc, dict) else exc}"

    notes = [f"reward={reward}", f"cached_input_tokens={n_cache}"]
    total_secs = _secs(res)
    if total_secs is not None:
        notes.append(f"trial_total_s={total_secs}")
    fr = info.get("failure_recovery")
    if fr:
        notes.append(f"fr_hints={fr.get('n_detect_hints')}")
        notes.append(f"fr_salvage={'/'.join(fr.get('salvage_fired') or []) or '-'}")
        notes.append(f"fr_injected_chars={fr.get('injected_chars')}")

    task_id = res.get("task_name", "").split("/")[-1]
    return {
        "提交同学": args.member,
        "方案/配置名称": args.config,
        "模型名称": ((res.get("config") or {}).get("agent") or {}).get("model_name", ""),
        "题目ID": task_id,
        "Run ID": res.get("trial_name", trial.name),
        "成功(1/0)": "" if reward is None else (1 if reward >= args.success_threshold else 0),
        "运行步数": (info.get("model_stats") or {}).get("api_calls", ""),
        "耗时(秒)": _secs(res.get("agent_execution")) or "",
        "Agent输入Token": n_in if msgs else "",
        "Agent输出Token": n_out if msgs else "",
        "Harness输入Token": 0 if args.harness_zero else "",
        "Harness输出Token": 0 if args.harness_zero else "",
        "Agent实际成本($)": "" if cost is None else round(cost, 6),
        "Harness实际成本($)": 0 if args.harness_zero else "",
        "总成本($)(自动)": "",
        "结束原因/失败原因": reason,
        "代码Commit": args.commit,
        "日志文件名/位置": str(trial),
        "备注": "; ".join(notes),
    }


def write_xlsx(rows: list[dict], path: Path) -> None:
    import openpyxl

    wb = openpyxl.load_workbook(path)
    ws = wb["逐题数据"]
    header = [c.value for c in ws[1]]
    assert header[: len(COLUMNS)] == COLUMNS, "column names in the sheet changed"
    r = 2
    while ws.cell(r, 1).value not in (None, ""):
        r += 1
    for row in rows:
        for ci, col in enumerate(COLUMNS, start=1):
            if col == "总成本($)(自动)":
                continue
            ws.cell(r, ci).value = row[col] if row[col] != "" else None
        r += 1
    wb.save(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir", type=Path)
    ap.add_argument("--member", required=True)
    ap.add_argument("--config", required=True, help="must match 方案说明 / 自动汇总 names, e.g. 乙-主")
    ap.add_argument("--commit", default="")
    ap.add_argument("--harness-zero", action="store_true", help="fill harness tokens/cost with 0 (no extra LLM calls)")
    ap.add_argument("--success-threshold", type=float, default=1.0)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--xlsx", type=Path, help="append rows into this copy of the group sheet")
    args = ap.parse_args()

    trials = sorted(p.parent for p in args.job_dir.glob("*/result.json"))
    rows = [trial_row(t, args) for t in trials]
    out = args.out or args.job_dir / f"rows_{args.config}.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    if args.xlsx:
        write_xlsx(rows, args.xlsx)

    ok = [r for r in rows if r["成功(1/0)"] != ""]
    costs = [r["Agent实际成本($)"] for r in rows if r["Agent实际成本($)"] != ""]
    print(f"{len(rows)} trials -> {out}")
    print(f"success {sum(r['成功(1/0)'] for r in ok)}/{len(ok)}; agent cost ${sum(costs):.4f}")
    errs = [r for r in rows if "Exception" in r["结束原因/失败原因"]]
    if errs:
        print(f"WARNING: {len(errs)} trial(s) with Harbor exceptions:", ", ".join(r["Run ID"] for r in errs))


if __name__ == "__main__":
    main()
