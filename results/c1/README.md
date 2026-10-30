# C1 merged preliminary results (32 of 40 tasks)

## Status

This is a **preliminary, incomplete C1 merge**, not a final 40-task C1 result.
The fixed configuration is `openrouter/particle-ai/particle-1`,
mini-SWE-agent 2.4.3, default `mini_base.yaml` harness, 30 steps, 900
seconds, and a USD 0.10 per-task cost-limit parameter.

## Source-selection policy

- Canonical indices 1–16: use the collaborator-supplied scored result when available.
- Canonical indices 17–40: use the local later C1 Harbor result.

This avoids silently mixing duplicate attempts. The two sources contain 11
duplicated task IDs; non-selected attempts remain in their original archive or
local job directory and are not treated as extra observations.

## Coverage and provisional metrics

- Available scored tasks: **32 / 40**.
- Missing: `000-count-nuclei`, `006-extract-gym-auditorium`,
  `012-hide-na-budget-values`, `021-fill-ramp-chart`,
  `036-license-eligibility`, `039-manchester-forecast`,
  `042-black-sale-coffee-makers`, and `045-united-bag-fee-page`.
- Positive-reward tasks: **17 / 32 (53.125%)**. This is not a valid final
  40-task success rate.
- Full reward: 13; partial reward: 4; zero reward: 15.
- Mean reward over available tasks: **0.476374**.
- Mean runtime: **546.31 seconds**.

`trajectory_usage_cost_usd` is the cost recorded in individual model
trajectories. It totals **USD 1.05679335** for these 32 selected rows, but must
not be presented as final C1 actual cost. The local 24-task portion has
independently recorded OpenRouter batch-usage deltas of **USD 0.65472222**,
whereas the collaborator archive has no compatible before/after batch snapshot.
Complete the eight missing tasks and collect compatible usage evidence before
reporting final C1 costs.

## Provenance

- Collaborator archive SHA256:
  `055daf7b63b613816bcbc4f0636e27168074e802b2308cee1f7869b3d0360fd6`.
- Local source artifacts (intentionally Git-ignored): `vendor/TUA-Bench/jobs/C1-particle-17-25/`,
  `vendor/TUA-Bench/jobs/C1-particle-task26-smoke-retry1/`, and
  `vendor/TUA-Bench/jobs/C1-particle-27-40/`.

No API key, OpenRouter key-usage response, or Docker credential is committed.

