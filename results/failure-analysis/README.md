# Failure-analysis package

This package is the lightweight, GitHub-shareable counterpart of local Harbor
run artefacts. It contains **87 candidates**: 70 from
Role 5 (R5-A, R5-A+B, R5-B) and 17 from CX/R3-A. A candidate is a
non-full-score completed run or an infrastructure-only run. Full-score runs are
excluded to keep review focused.

## Files

- `failure-candidates.csv` — the assignment sheet. Each row has outcome,
  cost/runtime, automatically detected signals, and empty reviewer fields.
- `trajectory-evidence.jsonl` — bounded command/output excerpts for each row;
  this is evidence, not a model-generated diagnosis.
- `manual-label-template.csv` — a clean sheet for reviewers to divide work.

## Recommended labels

Use one primary label per candidate: `task_misunderstanding`,
`wrong_or_incomplete_artifact`, `tool_or_command_error`, `repeated_ineffective_action`,
`timeout_or_step_limit`, `submission_or_verification_miss`, or
`infrastructure_failure`. Use `unclear` only if the bounded evidence cannot
support a decision. Put the decisive command/output in `evidence_summary`.

## Important interpretation rules

1. `automatic_signals` only searches the recorded command/output text. It is a
   triage aid, not proof of the failure cause.
2. Infrastructure-only Role 5 rows are retained but must not be counted as
   model failures or used in success-rate denominators.
3. Paths and raw artefacts are deliberately omitted. The original trajectories
   remain on the experiment machine under ignored `runs/`; the SHA-256 in the
   CSV lets the owner confirm that a reviewed local trajectory is the same one.
4. This package covers locally available R5 and CX trajectories. For C0/C1/R3/R4,
   use their tracked result files under `results/`; their raw traces were not
   present on this machine, so this exporter does not fabricate evidence.
