# Role 5 analysis protocol

**Status:** Defined before formal T1/T2 results are collected.  
**Unit of analysis:** One task under one configuration (`C0`, `T1`, or `T2`).

## Fixed comparison conditions

The formal comparison is valid only when C0, T1, and T2 use the same fixed
40-task list, model, mini-SWE-agent version, Harbor version, official verifier,
step limit, wall-time limit, and per-task cost cap. The only intended difference
is the Role 5 tool-interface setting:

| Configuration | Command Guard | Result Normalizer |
| --- | ---: | ---: |
| C0 | Off | Off |
| T1 | Off | On |
| T2 | On | On |

## Data inclusion and integrity rules

- Preserve one row for every attempted task/configuration.
- Keep normal failure, zero reward, timeout, and exception as observations.
- Exclude only `not_run` and documented `infrastructure_failure` rows from
  performance denominators. Keep them in the exported CSV and report their
  count separately.
- Keep every raw attempt in the CSV. When a task has more than one valid
  attempt because of a documented rerun, calculate metrics from the **last
  valid attempt in CSV order**; report earlier valid attempts as superseded.
  An infrastructure-only row never replaces a valid task result.
- Treat an empty failure-count field (`file_not_found`, `command_not_found`,
  `permission_denied`, `timeout_or_exception`, or `other_failures`) as zero.
  Other required numeric values remain mandatory.
- A task is **successful** only if `reward > 0` and `exception = NO`.
- Use `actual_openrouter_cost_usd`, measured as OpenRouter cumulative usage
  after minus before the run, when Harbor reports zero cost.
- Do not change a task's configuration, model, cap, or task set after seeing
  formal outcomes. Record any permitted infrastructure rerun in `notes`.

## Primary metrics

| Metric | Formula | Question answered |
| --- | --- | --- |
| Success rate | successful tasks / evaluable tasks | Does the tool layer solve more tasks? |
| Mean actual cost per task | total actual OpenRouter cost / evaluable tasks | Does it reduce cost per attempt? |
| Cost per success | total actual OpenRouter cost / successful tasks | Does it improve the cost-success trade-off? |
| Unproductive executed-action rate | `(file-not-found + command-not-found + permission-denied + timeout/exception + other failures) / total tool actions` | Does clearer feedback reduce commands that actually waste an execution turn? |

`evaluable tasks` are the last valid row for each task after excluding
`not_run` and `infrastructure_failure`. If no task succeeds, report cost per
success as `n.a.` rather than zero.

## Guard-specific audit metric

T2 may block a malformed request before the container executes it. Therefore
`guarded_actions / total_tool_actions` is reported **separately**, not folded
into the unproductive executed-action rate. This avoids unfairly treating a
prevented container execution as an executed failure. Inspect both measures:

- lower unproductive executed-action rate supports the value of clearer
  feedback and/or the guard;
- a non-zero guard rate shows how often T2 prevented a malformed request;
- a high guard rate without any cost or success improvement is a warning that
  the guard is only recording, not helping.

## Required comparisons and interpretation

1. **T1 vs C0:** isolates the Result Normalizer.
2. **T2 vs T1:** isolates the incremental Command Guard.
3. **T2 vs C0:** reports the complete Role 5 scheme, but does not by itself
   explain which component caused the change.

For each comparison, report the raw value for both configurations and the
difference (`candidate - reference`) for success rate and unproductive-action
rate. For cost metrics, a negative difference favors the candidate. Do not
claim causation from a small numerical change without discussing the 40-task
sample size and concrete trajectory examples.

## Reproducible summary command

Run the analysis against the raw result CSV with the project environment:

```bash
/opt/homebrew/bin/uv run python scripts/analyze_role5_results.py \
  --input results/role5/formal-results.csv \
  --output results/role5/analysis-summary.csv
```

The script validates numeric and categorical fields, calculates every metric
above, writes one summary row each for C0, T1, and T2, and reports raw,
excluded, and superseded attempt counts separately. It does not make a model
call or modify raw task artifacts.
