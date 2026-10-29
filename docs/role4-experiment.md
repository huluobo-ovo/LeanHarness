# Role 4 Experiment Record

This document records the Role 4 intervention, run commands, output locations,
and recovery decisions.  The final tables are in
[`results/role4/`](../results/role4/README.md).

## Intervention

R4-A provides a task-aware eight-step workflow: analyze requirements, inspect
the environment, implement, test, re-read the task, verify observable state,
repair if necessary, and submit only after verification.  R4-A+B is the full
design and adds a six-point mandatory verification block plus an explicit rule
against inspecting the benchmark verifier, reference solution, or hidden
evaluation files.

The research question is whether that mandatory block adds value beyond the
workflow alone.  The two YAML files differ only in that block.

## Environment preparation

The TUA-Bench project was installed with Python 3.12.15.  Docker Desktop ran
the task containers as `linux/amd64`.  The shared dependency repair was applied
to Harbor's installed mini-swe adapter before the pilot and formal runs:

```bash
adapter="$HOME/Documents/GitHub/PE6203-TUA-Bench-harness/.venv/lib/python3.12/site-packages/harbor/agents/installed/mini_swe_agent.py"
cp "$adapter" "$adapter.bak"
patch "$adapter" < "$HOME/Desktop/LeanHarness/contributions/liu-yalin/developer_pack/patches/harbor_miniswe_dependency_fix.patch"
```

This changes the adapter's installation command to install mini-swe-agent with
`litellm[proxy]`.  It is a shared compatibility repair, not part of R4-A or
R4-A+B.

## Canonical formal command

The configuration files had the old names shown in the comments at execution
time; they were subsequently renamed content-identically.  The following is
the reproducible command using the new names.  Set `CONFIG` and `OUTPUT` to one
of the two pairs below.

```bash
HARNESS="$HOME/Desktop/LeanHarness"
TUA="$HOME/Documents/GitHub/PE6203-TUA-Bench-harness"

# R4-A+B full (executed as configs/role4-pre-submit-main.yaml)
CONFIG="$HARNESS/configs/role4-workflow-mandatory.yaml"
OUTPUT="$HARNESS/results/raw/role4-main-40"

# R4-A ablation (executed as configs/role4-pre-submit-ablation.yaml)
# CONFIG="$HARNESS/configs/role4-workflow-only.yaml"
# OUTPUT="$HARNESS/results/raw/role4-ablation-40"

task_args=()
while IFS= read -r task; do
  [[ -z "$task" || "$task" == \#* ]] && continue
  task_args+=(-p "$TUA/tasks/$task")
done < "$HARNESS/configs/task_list_40.txt"

DOCKER_DEFAULT_PLATFORM=linux/amd64 caffeinate -i \
  uv --project "$TUA" run harbor run \
  "${task_args[@]}" \
  -a mini-swe-agent \
  -m openrouter/minimax/minimax-m3.1-flash \
  --agent-kwarg version=2.4.3 \
  --agent-kwarg config_file="$CONFIG" \
  --agent-kwarg cost_limit=0.06 \
  --agent-setup-timeout-multiplier 4 \
  -n 2 \
  -o "$OUTPUT" \
  --yes
```

`-n 2` allowed two concurrent trials.  The `caffeinate -i` wrapper prevented
idle system sleep; display sleep was harmless.  The runtime warning about a
different active virtual environment was informational because `uv --project`
selected the TUA-Bench project environment explicitly.

## Pilot

R4-A+B was tested on `000-count-nuclei` before the formal batch.  Its final
pilot invocation used the same model and arguments as above, with one task,
`-n 1`, and output directory
`results/raw/role4-pilot-main-amd64-timeout`.  The final pilot had one trial,
zero Harbor exceptions, and reward 0.  The zero reward is valid because the
pilot was a chain-health check.

R4-A did not receive a separate successful pre-formal pilot.  This is recorded
as a protocol deviation rather than being reconstructed after the fact.

## Formal and recovery artifacts

| Configuration | Initial formal job | Infrastructure replacement job |
| --- | --- | --- |
| R4-A+B | `results/raw/role4-main-40/2026-10-27__18-23-13` | `results/raw/role4-main-infra-reruns/2026-10-28__08-29-58` |
| R4-A | `results/raw/role4-ablation-40/2026-10-29__01-25-13` | `results/raw/role4-ablation-infra-reruns/2026-10-29__08-07-08` |

R4-A+B infrastructure replacements:

```text
003-rebuild-energy-model
054-prostate-label-obj
057-set-undo-steps-100
063-red-slide-numbers
072-save-speedtest-results
```

R4-A infrastructure replacements:

```text
000-count-nuclei
012-hide-na-budget-values
036-license-eligibility
042-black-sale-coffee-makers
045-united-bag-fee-page
066-set-slide-image-heights
069-linux-ls-tutorial
078-add-wednesday-lecture
081-video-frame-slide-bg
084-plate-thermal-sim
090-ecs-grf-pass-rates
102-daily-email-report
105-search-cell-b6
114-nuclei-csv-open
117-comma-text-to-table
```

The recovery command was the canonical formal command with `task_args` built
from only the relevant list above and the corresponding replacement output
directory.  No zero-reward, 30-step-limit, or 900-second agent-limit outcome
was rerun.

## Result construction and validation

Run:

```bash
python3 scripts/build_role4_results.py
```

The script requires exactly 40 unique tasks per initial configuration, requires
the replacement set to match the initial exception set exactly, rejects any
final exception or unfinished result, selects the allowed replacement, and
generates all Role 4 CSV tables plus a SHA-256 manifest for the local raw
artifacts.

OpenRouter usage was recorded as USD 2.6178 before R4-A+B and USD 3.6417 after
its formal run and infrastructure replacements, so its measured cost was USD
1.0239 (USD 0.0256 per task when divided across the final 40-task table).
OpenRouter usage was USD 4.8642 after R4-A and its infrastructure replacements,
so R4-A's measured cost was USD 1.2225 (USD 0.0306 per task).  The combined
Role 4 cost was USD 2.2464.  These account deltas are batch-level evidence; the
per-task `actual_openrouter_cost_usd` cells remain blank because OpenRouter did
not provide an auditable task-level allocation and Harbor reported `0.0`.

## Known limitations

1. The shared C0 table is not yet present, so only the internal R4-A versus
   R4-A+B paired analysis is complete.
2. R4-A lacks a successful pre-formal pilot.
3. R4-A trajectories contain six attempted `/logs/verifier` directory probes.
   No verifier files were exposed, but the attempts are documented in
   `results/role4/compliance-audit.csv`; R4-A+B has no such probe.
4. Raw logs and trajectories are retained locally and hash-manifested, but are
   intentionally not committed under the repository's raw-artifact policy.
