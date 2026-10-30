# R3 experiment result summaries (Yichen Tang)

This directory records the auditable, per-task result summaries submitted by
Yichen Tang for three R3 configurations:

| File | Configuration in source | Tasks | Model | Code commit |
| --- | --- | ---: | --- | --- |
| `yichen_tang_R3-A_per_task.csv` | R3-A | 40 | `openrouter/minimax/minimax-m3.1-flash` | `961bb9c` |
| `yichen_tang_R3-B_per_task.csv` | R3-B | 40 | `openrouter/minimax/minimax-m3.1-flash` | `2d29715` |
| `yichen_tang_R3-A+B_per_task.csv` | R3-A+B | 40 | `openrouter/minimax/minimax-m3.1-flash` | `961bb9c` |

All three CSV files contain the same 40 task IDs with no duplicates. The
source fields retain the submitted run ID, success flag, steps, duration,
token counts, agent cost, termination reason, code commit, log location, and
the reward recorded in `备注`.

## Provenance

Imported from `yichen.tang_R3_完整实验材料(1).zip` supplied on 30 October
2026. SHA-256 of the supplied archive:

`4cf6d54a0542f34baf6f5d72163ca94e66d0f0a09f2207b800b50348aeeb2118`

The submitted archive also contains raw Harbor job artifacts (about 274 MB).
They are intentionally not committed here: the CSV summaries are the
reviewable experiment record, while committing generated container/log
artifacts would unnecessarily enlarge normal Git clones. Keep the original
archive in the team's shared storage and use the hash above to verify it.

## Data notes

- No OpenRouter key or authorization value was found in the three committed
  CSV files.
- `Harness输入Token` and `Harness输出Token` are zero in the submitted data.
  Therefore do not infer a separate harness API cost from these columns.
- The source `总成本($)(自动)` field is retained verbatim. Use the submitted
  `Agent实际成本($)` field for the recorded model-side cost unless the team
  later supplies an independently validated total-cost calculation.
