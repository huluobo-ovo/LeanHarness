# Role 4: Pre-Submission Verification

Role 4 tests whether a task-aware verification workflow improves reliable task
completion before the agent submits its work.  The experiment follows the
fixed 40-task protocol in the updated member README.

## Configurations and hypothesis

| ID | Configuration | Purpose |
| --- | --- | --- |
| R4-A+B | [`configs/role4-workflow-mandatory.yaml`](../../configs/role4-workflow-mandatory.yaml) | Full design: an eight-step workflow plus a mandatory pre-submission verification block. |
| R4-A | [`configs/role4-workflow-only.yaml`](../../configs/role4-workflow-only.yaml) | Ablation: keeps the workflow but removes the mandatory block. |

The hypothesis was that making the final verification block mandatory would
increase successful completion by forcing a final requirement check.  The
ablation isolates that block; all other configuration text is identical.

The files were named `role4-pre-submit-main.yaml` and
`role4-pre-submit-ablation.yaml` when the runs were executed.  They were renamed
afterward for clarity without changing their contents.  SHA-256:

- R4-A+B: `1f375060c4273851f1a6e2445e812893e8fa8473f428c4169d3209095a3d6cf3`
- R4-A: `1476bd44eaab32549df12d6ca1f9d28cc50baea3f2c71e12fbb905c5a58d5648`
- fixed task list: `dda7a545967f07dc5dead08ab02d6420486b4bf9c3a127884aa6a6b98c960bee`

## Fixed environment

- TUA-Bench commit: `3497fd320abcafaf4797424192c891a593fd7964`
- Harbor `0.6.3`, mini-swe-agent `2.4.3`, Python `3.12.15`
- model: `openrouter/minimax/minimax-m3.1-flash`
- 40 fixed tasks, 30 agent steps, 900-second agent wall-time limit, USD 0.06
  per-task launch limit
- Apple Silicon runs used `DOCKER_DEFAULT_PLATFORM=linux/amd64`
- the shared Harbor dependency patch added `litellm[proxy]` when installing
  mini-swe-agent; this was an environment compatibility fix, not a Role 4
  intervention

## Final results

These figures use exactly one valid final result for each of the 40 tasks.
Ordinary zero-reward results and enforced-limit results are retained.  Only
documented infrastructure failures were replaced.

| Metric | R4-A+B full | R4-A ablation |
| --- | ---: | ---: |
| Tasks | 40 | 40 |
| Total reward | 16.463543 | 19.059501 |
| Mean reward | 0.411589 | 0.476488 |
| Positive-reward tasks | 17 | 20 |
| Full-reward tasks | 15 | 18 |
| Partial-reward tasks | 2 | 2 |
| Zero-reward tasks | 23 | 20 |
| Completion command issued | 14 | 21 |
| 30-step limit reached | 23 | 19 |
| 900-second agent limit reached | 3 | 0 |
| Mean agent runtime (seconds) | 389.866 | 244.152 |
| Input / cache / output tokens | 24,348,264 / 23,003,776 / 789,391 | 26,268,783 / 24,060,616 / 867,333 |
| Actual OpenRouter batch cost | USD 1.0239 | USD 1.2225 |
| Average actual cost per final task | USD 0.0256 | USD 0.0306 |

On the paired task comparison, R4-A and R4-A+B tied on 30 tasks, R4-A was
better on 7, and R4-A+B was better on 3.  The ablation improved mean reward by
`0.064899`, so the mandatory block did not support the original performance
hypothesis under this run.

The two Role 4 configurations consumed USD 2.2464 in total.  R4-A+B was
measured from OpenRouter cumulative usage USD 2.6178 to USD 3.6417; R4-A was
measured from USD 3.6417 to USD 4.8642.  These are batch-level account deltas,
so they are reported in the configuration summary rather than assigned to
individual task rows.

The three R4-A+B `TimeExceeded` records are
`051-hide-left-dock`, `084-plate-thermal-sim`, and
`090-ecs-grf-pass-rates`.  They are completed benchmark outcomes, not
infrastructure exceptions, and were not rerun.

## Reruns and integrity notes

- R4-A+B had 5 initial infrastructure exceptions; R4-A had 15.  Every one and
  only those tasks was rerun.  The failure reason and replacement trial are in
  [`infrastructure-reruns.csv`](infrastructure-reruns.csv).
- R4-A+B had a successful one-task pilot with Harbor Exceptions = 0 before its
  formal run.  Two earlier infrastructure-failed attempts are also recorded in
  [`pilot-results.csv`](pilot-results.csv).
- R4-A did not receive a separate successful pre-formal pilot.  This is a
  protocol deviation and must remain disclosed.
- A trajectory audit found that R4-A issued commands referencing
  `/logs/verifier` on 6 tasks.  The directory listings were empty and no
  verifier file path or content was returned, but the attempted probes are a
  compliance concern.  R4-A+B had no such command.  See
  [`compliance-audit.csv`](compliance-audit.csv).  For a single compliance-safe
  team submission, R4-A+B should therefore be treated as the primary Role 4
  configuration even though R4-A scored higher.
- Comparison with the shared C0 remains pending until the C0 40-task table is
  available in this repository.

## Files in this result package

- [`formal-results.csv`](formal-results.csv): 80 valid final per-task rows
  (40 for each configuration).
- [`summary.csv`](summary.csv): configuration-level totals and limits.
- [`paired-comparison.csv`](paired-comparison.csv): task-by-task ablation
  comparison.
- [`infrastructure-reruns.csv`](infrastructure-reruns.csv): all 20 permitted
  infrastructure replacements.
- [`pilot-results.csv`](pilot-results.csv): the three R4-A+B pilot attempts.
- [`compliance-audit.csv`](compliance-audit.csv): protected-path probe audit.
- [`raw-artifact-manifest.csv`](raw-artifact-manifest.csv): SHA-256 manifest of
  the retained raw results, logs, trajectories, verifier outputs, and task
  artifacts.

The raw artifacts occupy about 102 MiB under the ignored local
`results/raw/role4-*` directories.  They are retained locally and are covered by
the manifest, but are not committed because the repository README explicitly
says raw run artifacts should not be submitted to GitHub.  They should be
copied separately if the course submission channel requires them.  No API key
or `.env` file is included.

Exact reproducibility commands and local artifact locations are documented in
[`docs/role4-experiment.md`](../../docs/role4-experiment.md).
