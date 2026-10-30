# Role 4 GitHub Submission Memo

The Role 4 GitHub package contains the three configurations, reproducibility and
analysis documentation, generated result tables, and the deterministic table
builder.  It does not contain secrets or the ignored 215 MiB raw artifact tree.

## Configurations

- `configs/role4-workflow-mandatory.yaml`: R4-A+B full configuration; this is
  the compliance-safe primary configuration for a single-version submission.
- `configs/role4-workflow-only.yaml`: R4-A ablation; higher observed reward but
  retained as an ablation because six trajectories attempted empty verifier
  path probes.
- `configs/role4-mandatory-only.yaml`: R4-B ablation; the original six-step
  baseline workflow plus only the mandatory verification block.  It has the
  highest observed reward of the three runs and no verifier-path probes, but no
  separate successful pre-formal pilot.

## Results and audit evidence

- `results/role4/formal-results.csv`: all 120 valid final task records.
- `results/role4/summary.csv`: three configuration summaries.
- `results/role4/paired-comparison.csv`: 40 paired reward comparisons across
  R4-A+B, R4-A, and R4-B.
- `results/role4/infrastructure-reruns.csv`: reasons and replacements for all
  20 permitted infrastructure reruns.
- `results/role4/pilot-results.csv`: all three R4-A+B pilot attempts.
- `results/role4/compliance-audit.csv`: the six R4-A verifier-path probes.
- `results/role4/raw-artifact-manifest.csv`: paths, sizes, and SHA-256 hashes of
  the retained local raw artifacts.
- `results/role4/README.md`: hypothesis, fixed settings, metrics, limitations,
  and interpretation.

## Reproducibility

- `docs/role4-experiment.md`: exact formal command pattern, pilot, rerun lists,
  artifact locations, cost measurement, and known limitations.
- `scripts/build_role4_results.py`: rebuilds and validates every Role 4 result
  and audit table from the local Harbor artifacts.

Raw results, logs, trajectories, verifier outputs, and task artifacts remain
under the ignored local `results/raw/role4-*` directories.  They are not in Git
history because the repository README says raw run artifacts should not be
submitted to GitHub.  Use `raw-artifact-manifest.csv` to verify a separate
course-submission copy.  No `.env`, API key, or `harbor upload` output is part
of this package.
