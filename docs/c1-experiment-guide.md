# C1 expensive-model baseline guide

## What C1 measures

C1 is the stronger, more expensive model under the **default harness**.  It
uses the same 40 tasks, 30-step cap, 900-second time limit, mini-SWE-agent
2.4.3, Harbor 0.6.3, and task verifier as C0.  Both Command Guard and Result
Normalizer are off.  This is the reference for the project question: can a
less expensive model plus a harness intervention approach or exceed the
expensive model's default-harness performance at lower cost?

## Before a paid run

1. The team must record one exact OpenRouter model ID for C1. Do not silently
   substitute the inexpensive C0/T1/T2/T3 model.
2. Confirm the model is available to the OpenRouter key and is appropriate for
   tool calling.
3. Record the OpenRouter cumulative usage before starting. The final actual
   cost is the after-minus-before difference; Harbor may display zero cost.
4. Run one smoke task first. It must finish with `Exceptions = 0`.

## Dry run

This checks command construction only and makes no model call:

```bash
/opt/homebrew/bin/uv run python scripts/run_role5_batch.py \
  --configuration C1 \
  --task 000-count-nuclei \
  --model openrouter/TEAM-APPROVED-EXPENSIVE-MODEL \
  --dry-run
```

## Formal run

The C1 per-task cap is USD 0.10. Run tasks once and sequentially. Do not rerun
ordinary failures or zero rewards. Only retry documented infrastructure
failures after team approval.

```bash
/opt/homebrew/bin/uv run python scripts/run_role5_batch.py \
  --configuration C1 \
  --task 000-count-nuclei \
  --model openrouter/TEAM-APPROVED-EXPENSIVE-MODEL
```

Results are written locally to `results/c1/c1-results.csv`; raw trial artifacts
go to `runs/c1-formal/`. Keep both for audit and do not commit API keys.
