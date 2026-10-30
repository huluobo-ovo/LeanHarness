# C1 merged results (40 of 40 tasks)

## Status

This is a merged C1 40-task result record. Its cost evidence retains source
limitations described below.
The fixed configuration is `openrouter/particle-ai/particle-1`,
mini-SWE-agent 2.4.3, default `mini_base.yaml` harness, 30 steps, 900
seconds, and a USD 0.10 per-task cost-limit parameter.

## Source-selection policy

- Canonical indices 1–16: use the collaborator-supplied scored result when available.
- Canonical indices 17–40: use the local later C1 Harbor result.

The six formerly missing tasks (`000`, `006`, `012`, `021`, `036`, and `042`)
come from the later collaborator current snapshot. The final two (`039` and
`045`) come from the local dedicated missing-task run.

This avoids silently mixing duplicate attempts. Non-selected duplicate attempts
remain in their original archive or local job directory and are not treated as
extra observations.

## Coverage and result metrics

- Available scored tasks: **40 / 40**.
- Positive-reward tasks: **24 / 40 (60.0%)**.
- Full reward: 19; partial reward: 5; zero reward: 16.
- Mean reward: **0.547599**.
- Mean runtime: **620.53 seconds**.

`trajectory_usage_cost_usd` is the cost recorded in individual model
trajectories. It totals **USD 1.31072142** for the 40 selected rows and has an
average of **USD 0.03276804** per task. It is not identical to the OpenRouter
usage-difference method. In particular, the two locally completed final tasks
(`039` and `045`) have a combined OpenRouter usage delta of **USD 0.029876534**;
their trajectory costs are kept per task for audit, not asserted as two
separate actual-cost measurements. The collaborator sources lack one compatible
whole-batch usage snapshot, so report the cost method and limitation alongside
any C1 cost comparison.

## Provenance

- Collaborator archive SHA256:
  `055daf7b63b613816bcbc4f0636e27168074e802b2308cee1f7869b3d0360fd6`.
- Collaborator current snapshot supplied on 2026-10-30, SHA256
  `d828c344049220396494b85e465298c6d96fb2b6db0644acfce2f6c1b507f43a`,
  containing original artifacts for the six newly included tasks.
- Local source artifacts (intentionally Git-ignored): `vendor/TUA-Bench/jobs/C1-particle-17-25/`,
  `vendor/TUA-Bench/jobs/C1-particle-task26-smoke-retry1/`, and
  `vendor/TUA-Bench/jobs/C1-particle-27-40/`.

No API key, OpenRouter key-usage response, or Docker credential is committed.

