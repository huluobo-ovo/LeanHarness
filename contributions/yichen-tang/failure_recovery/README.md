# Failure recovery (role 3)

Branch: `feature/role3-failure-recovery`

Same base config, model and limits as `mini_base.yaml` (30 steps, 900 s). The only
change is the agent class. It does not make extra LLM calls.

- `fr_detect`: after each step, check for command timeouts, 2 failed steps in a row,
  repeated commands, and the required output file still missing after 8 steps. If
  something is found, add a short hint for the model.
- `fr_salvage`: when 5 steps (or 150 s) are left, tell the model to save its current
  result and submit. One more reminder at 2 steps left.

Configs:

- `failure-recovery-main.yaml`: detect + salvage
- `failure-recovery-ablation.yaml`: detect only

Motivation: in the C0 example run (000-count-nuclei) the agent used all 30 steps
exploring and never wrote `/app/artifacts/nuclei_count.txt`, so it scored 0.

## Files

- `fr_agent.py`: the agent (subclass of mini-swe-agent `InteractiveAgent`). Hints are
  logged in the trajectory under `info.failure_recovery`.
- `failure_recovery_harbor.py`: Harbor agent that copies `fr_agent.py` into the
  container after the normal mini-swe-agent install.
- `export_rows.py`: converts a Harbor job folder into rows for the group sheet.
- `tests/`: offline tests with a scripted model (no API key or Docker needed).

## Run

From `vendor/TUA-Bench`, with `OPENROUTER_API_KEY` exported in the shell:

```bash
FR=~/pe6203/LeanHarness/contributions/yichen-tang/failure_recovery

PYTHONPATH=$FR uv run harbor run \
  -p tasks/000-count-nuclei \
  --agent-import-path failure_recovery_harbor:FailureRecoveryMiniSweAgent \
  -m openrouter/<model> \
  --agent-kwarg version=2.4.3 \
  --agent-kwarg config_file=$FR/failure-recovery-main.yaml \
  --agent-kwarg cost_limit=0.06 \
  -n 1 -o jobs/fr-dev --yes
```

For the ablation use `failure-recovery-ablation.yaml`. For the 40 tasks, use the same
task selection as the C0 run, e.g.
`-p tasks $(grep -v '^#' ../../configs/task_list_40.txt | sed 's/^/-i /')`.

Check after a run:

- `n_errors` is 0 in the job `result.json`
- `trial.log` shows the `cp /tmp/fr_agent.py` command without an install error
- the trajectory has `info.config.agent_type = fr_agent.FailureRecoveryAgent`

## Export

```bash
python export_rows.py jobs/fr-main/<job> --member 3号 --config 乙-主 --commit <sha> --harness-zero --xlsx sheet.xlsx
```

Harness tokens and cost are 0 because no extra model calls are made. The added hint
text is already included in the agent input tokens (`fr_injected_chars` in the notes).

## Tests

```bash
uv run --with mini-swe-agent==2.4.3 --with pytest pytest tests
```

## Limitations

- Output paths are taken from the task text with simple rules. If no path is found,
  it falls back to checking whether any command wrote something.
- Thresholds were set from one C0 trajectory and not tuned.
- Each config is run once.
