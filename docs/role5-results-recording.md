# Role 5 results recording

Use `templates/role5-results-tracker.xlsx` for the working record and keep a
machine-readable copy in `templates/role5-results-records.csv` or a run-specific
CSV under `results/role5/`. Record one row for every task and configuration.

## Required fields

- **Configuration:** `C0`, `T1`, or `T2`.
- **Task ID, model, agent version, adapter commit:** identifies precisely what
  was run.
- **Reward and exception:** copy the official Harbor/verifier outcome exactly.
- **Runtime and token counts:** copy from the run artifacts.
- **Actual OpenRouter cost:** calculate from cumulative usage immediately
  before and after the run. Harbor may display `0.0` for this provider.
- **Tool/failure counts:** obtain from the saved mini-SWE-agent trajectory.
  For T2, `guarded_actions` counts results with `leanharness_guarded: true`.
- **Trajectory and Harbor output paths:** keep evidence auditable.

## Metrics for the report

Calculate results separately for C0, T1, and T2:

| Metric | Formula | Role 5 interpretation |
| --- | --- | --- |
| Success rate | successful tasks / completed tasks | Does the intervention solve more tasks? |
| Average actual cost | total actual cost / completed tasks | Does it reduce spend per attempt? |
| Cost per success | total actual cost / successful tasks | Does it improve the cost-success trade-off? |
| Failure-action rate | failure actions / total tool actions | Do Guard/Normalizer reduce repeated unproductive actions? |

Treat normal failure, zero reward, timeout, and a non-zero result as evidence,
not as rows to delete. A rerun is allowed only for a documented infrastructure
failure.
