# Role 5 T1/T2 formal test plan

**Owner:** Role 5  
**Scope:** T1 and T2 only. C0 is the shared baseline owned by Role 1.  
**Status:** Ready after the T1 smoke check; T2 smoke check has passed.

## Question being tested

The experiment holds the task list, model, maximum steps (30), task time limit
(900 seconds), and per-task cost cap (USD 0.06) constant.  It changes only the
tool interface:

| Condition | Tool-interface change | Formal runs |
| --- | --- | ---: |
| T1 | Result Normalizer | 40 |
| T2 | Result Normalizer + Command Guard | 40 |

This produces 80 formal Role 5 runs.  C0's 40 runs are separate and should be
supplied by Role 1 for the final comparison.

## Preconditions and stop rules

Before a paid batch:

1. Use the same CLI model name for every T1/T2 run: `openrouter/minimax/minimax-m3.1-flash`.
2. Run the test suite and config validation successfully.
3. Confirm the Harbor adapter patch is installed and the local `.env` contains
   `OPENROUTER_API_KEY` (never commit the key).
4. Keep at most **two** trials executing at one time on the shared Mac/Docker
   machine.
5. Stop the batch and investigate if two consecutive tasks fail due to the same
   infrastructure issue, or if a task reports an adapter/trajectory error.

A zero reward or an agent time/step limit is an experimental outcome, not an
infrastructure failure.  Record it and do not silently rerun it.  Rerun only a
documented infrastructure failure (for example Docker daemon, image build, or
network failure before the agent starts).

## Batch layout

Use the canonical order in `configs/task_list_40.txt`.  Each batch has 10
tasks; run at most two tasks concurrently within the batch.

| Batch | Condition | Tasks (line numbers in the 40-task list) | Maximum cost |
| --- | --- | --- | ---: |
| 1 | T1 | 1-10 | USD 0.60 |
| 2 | T1 | 11-20 | USD 0.60 |
| 3 | T1 | 21-30 | USD 0.60 |
| 4 | T1 | 31-40 | USD 0.60 |
| 5 | T2 | 1-10 | USD 0.60 |
| 6 | T2 | 11-20 | USD 0.60 |
| 7 | T2 | 21-30 | USD 0.60 |
| 8 | T2 | 31-40 | USD 0.60 |

The hard upper bound is USD 4.80 for 80 formal runs.  Actual cost may be lower.
The earlier T2 smoke run is validation evidence and is not counted as part of
these 80 formal runs.

## Checkpoint after each batch

1. Confirm every trial has a saved `result.json`, trajectory, and agent log.
2. Record task ID, condition, reward, exception state, elapsed time, tokens,
   and raw OpenRouter cost in `templates/role5-results-tracker.xlsx`.
3. Count normal outcomes, infrastructure reruns, and unspent/actual budget.
4. Do not change T1/T2 parameters during the 80-run formal phase.

## Recommended operating rhythm

Run one 10-task batch per scheduled session.  On a typical task, two parallel
trials should finish in roughly 30-90 minutes; initial Docker image builds and
hard tasks can take longer.  The schedule should leave a two-hour window and
run only while the laptop is awake, powered, and connected to the internet.

## After all 80 runs

Use `scripts/analyze_role5_results.py` and the analysis protocol to compare
T1 vs C0, T2 vs C0, and T2 vs T1.  If a later improvement is desired, create a
new condition (for example T3) and identify it as an exploratory second round;
do not overwrite T1/T2's preregistered results.
