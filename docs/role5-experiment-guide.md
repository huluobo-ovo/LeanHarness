# Role 5 T1/T2/T3 experiment guide

**Owner:** Role 5  
**Status:** Candidate configurations ready; real Harbor adapter integration still required

## What the configurations compare

| ID | Guard | Result normalizer | Question being tested |
| --- | --- | --- | --- |
| C0 | Off | Off | Shared default-harness baseline, run by Role 1. |
| T1 | Off | On | Does concise, structured command feedback improve success or reduce wasted turns? |
| T2 | On | On | Does also rejecting clearly malformed commands improve the cost-success trade-off? |
| T3 | On | Off | Does Command Guard alone improve the cost-success trade-off? |

The three Role 5 configurations differ only in `guard_enabled` and
`normalizer_enabled`. They use the same
40 tasks, provider, future team-selected model, 30-step limit, 900-second task
limit, and USD 0.06 per-task cap. This keeps the comparison attributable to the
tool-interface intervention instead of a different model, budget, or task set.

## Files to use

- `configs/tool-interface-normalizer.yaml`: T1, result normalizer only.
- `configs/tool-interface-complete.yaml`: T2, command guard plus normalizer.
- `configs/tool-interface-command-guard.yaml`: T3, command guard only.
- `configs/task_list_40.txt`: canonical fixed evaluation set.
- `contributions/liu-yalin/developer_pack/settings/mini_base.yaml`: shared
  mini-SWE-agent base configuration submitted by Liu Yalin.

## Safe checks before any paid run

```bash
/opt/homebrew/bin/uv run --group dev pytest
/opt/homebrew/bin/python3.12 scripts/validate_role5_configs.py
```

Both must pass before a model call. These commands do not need Docker or an API
key and do not contact OpenRouter.

## Required decisions before the one-task smoke run

1. The team records one OpenRouter model name in both YAML files, replacing
   `TEAM_DECISION_REQUIRED`.
2. Role 1 publishes or confirms the Harbor/mini-SWE-agent adapter integration
   point. Upstream mini-SWE-agent does not yet read the `leanharness` block.
3. The local `.env` contains a personal/team OpenRouter key; never commit it.
4. The Harbor mini-SWE-agent dependency compatibility fix has been applied
   consistently and disclosed as an environment fix, not as a harness change.

## One-task smoke run protocol

Before the 40-task batch, run exactly one agreed development task through the
shared adapter with T1, T2, or T3. Keep the exact command in the experiment
log after Role 1 finalizes the adapter command. A valid smoke run requires:

- Harbor reports `Exceptions = 0`;
- the saved trajectory contains the expected `leanharness_*` feedback fields;
- the task ID, configuration ID, model, elapsed time, tokens, and OpenRouter
  usage-before/usage-after snapshots are recorded;
- raw Harbor output, agent log, and trajectory are retained.

Do not start a 40-task paid batch until the smoke run meets all four checks.

## Formal 40-task run protocol

Run T1, T2, and T3 once each after the team locks the model and adapter revision.
Normal failure, zero reward, timeout, and non-zero task results are evidence;
do not delete or rerun them. Only an infrastructure failure may be rerun, with
the reason recorded. Retain output under the per-configuration `run_root` in
the YAML and publish a summary containing task ID, reward, exception status,
runtime, input/output tokens, and actual OpenRouter cost.

## Interpretation rule

T1 answers whether clearer feedback helps. T3 answers whether the Command
Guard helps alone. Comparing T2 with T1 isolates the incremental effect of the
Command Guard, while comparing T2 with T3 isolates the incremental effect of
the Result Normalizer. Compare each variant with C0 as the default harness.
