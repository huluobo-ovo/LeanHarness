# CX R3-A detect-only formal results

## Result

| Metric | Value |
| --- | ---: |
| Tasks | 40 |
| Mean reward | 0.6406731358 |
| Total reward | 25.6269254336 |
| Full / partial / zero reward | 23 / 5 / 12 |
| Harbor exceptions | 0 |
| Automatic retries | 0 |
| Actual OpenRouter cost | USD 0.897652674 |
| Average actual cost per task | USD 0.022441317 |

## Fixed setup

- Configuration: CX, R3-A / Failure Recovery detect-only.
- Agent config: `contributions/yichen-tang/failure_recovery/failure-recovery-ablation.yaml` (`fr_detect=true`, `fr_salvage=false`).
- Model: `openrouter/particle-ai/particle-1`; mini-SWE-agent 2.4.3; Harbor 0.6.3; Python 3.12.15.
- Platform/concurrency/limits: linux/amd64, one concurrent task, 30 steps and 900 seconds per task, nominal USD 0.10 agent cost limit.
- Source jobs: smoke task `000-count-nuclei` in `cx-r3a-20261030-193259`, then the 39-task batch in `cx-r3a-20261030-1948`.

## Cost and provenance note

Harbor wrote `cost_usd=0.0` for every result despite OpenRouter costs being present in the raw agent trajectories. `formal-results.csv` therefore uses the sum of every trajectory response's `cost_details.upstream_inference_cost` as the actual model cost. Two trials exceeded the nominal USD 0.10 limit: 033-prostate-volume-est (USD 0.111104222), 054-prostate-label-obj (USD 0.113809458). This is a cost-accounting/limit-enforcement observation, not an infrastructure failure.

Raw Harbor artifacts, logs, trajectories, verifier output, and task artifacts remain in the ignored local `runs/cx-r3-a/` directory. They are not committed to keep the repository lean and avoid accidental inclusion of local material.

## Files

- `formal-results.csv`: one final row for each of the 40 tasks.
- `TEAM_NOTE_CN.md`: concise Chinese handoff message for teammates.
