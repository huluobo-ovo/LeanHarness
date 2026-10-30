# Role 5 Harbor 0.6.3 integration

This is the reproducible connection between LeanHarness Role 5's tool
interface and the real `mini-swe-agent` process launched by Harbor 0.6.3.
It is intentionally a **version-locked, reversible adapter patch** rather than
a permanent manual edit to `.venv/site-packages`.

## What is changed

The patch makes Harbor's installed `mini_swe_agent.py` accept one additional
agent kwarg: `role5_config_file`. When supplied, it reads only
`leanharness.tool_interface` from the selected R5-A or R5-A+B YAML, creates a private
in-container copy of `mini_base.yaml`, installs the repository-versioned
`adapters/role5_runtime_agent.py` overlay, then starts mini-SWE-agent normally.

The overlay subclasses the default agent. R5-A normalizes each `env.execute`
result; R5-A+B also intercepts malformed actions before that call. It preserves
the standard action, output, return code, exception, and `tool_call_id`
contracts, so Harbor trajectory conversion and the official verifier remain
unchanged.

The patch also applies the shared Harbor compatibility fix from Liu Yalin's
developer pack: it installs mini-SWE-agent with `litellm[proxy]`, which supplies
the MCP dependency needed by the OpenRouter/LiteLLM stack. This is an
environment fix, not a Role 5 harness intervention, and must stay identical
for C0, R5-A, and R5-A+B.

## Compatibility contract

- Harbor: **0.6.3**
- mini-SWE-agent: **2.4.3** for the official run
- Python: **3.12.15**
- Base config: `contributions/liu-yalin/developer_pack/settings/mini_base.yaml`
- Do not edit that shared base YAML.

The patch rejects an unrecognised adapter layout instead of guessing. It keeps
an adjacent `.leanharness-role5.bak` copy and supports restoration.

## Apply once per local TUA-Bench environment

From `vendor/TUA-Bench`, with `/path/to/LeanHarness` replaced by the local
repository root:

```bash
PYTHONPATH=/path/to/LeanHarness/src \
  uv run python /path/to/LeanHarness/scripts/manage_role5_harbor_adapter.py apply
```

Confirm the target file is reported by:

```bash
uv run python -c 'import harbor.agents.installed.mini_swe_agent as m; print(m.__file__)'
```

To restore the exact original adapter:

```bash
PYTHONPATH=/path/to/LeanHarness/src \
  uv run python /path/to/LeanHarness/scripts/manage_role5_harbor_adapter.py restore
```

Do not commit the resulting `.venv` edit or the backup file. The repository
script and runtime overlay are the reproducible artifact.

## One-task compatibility commands

After applying the patch and configuring a local API key, run exactly one task
before any batch. Only the Role 5 YAML differs between commands.

### R5-A — Result Normalizer only

```bash
uv run harbor run -p tasks/000-count-nuclei -a mini-swe-agent \
  -m openrouter/minimax/minimax-m3.1-flash \
  --agent-kwarg version=2.4.3 \
  --agent-kwarg config_file=/path/to/LeanHarness/contributions/liu-yalin/developer_pack/settings/mini_base.yaml \
  --agent-kwarg role5_config_file=/path/to/LeanHarness/configs/tool-interface-normalizer.yaml \
  --agent-kwarg cost_limit=0.06 -o jobs/role5-t1-smoke --yes
```

### R5-A+B — Command Guard plus Result Normalizer

```bash
uv run harbor run -p tasks/000-count-nuclei -a mini-swe-agent \
  -m openrouter/minimax/minimax-m3.1-flash \
  --agent-kwarg version=2.4.3 \
  --agent-kwarg config_file=/path/to/LeanHarness/contributions/liu-yalin/developer_pack/settings/mini_base.yaml \
  --agent-kwarg role5_config_file=/path/to/LeanHarness/configs/tool-interface-complete.yaml \
  --agent-kwarg cost_limit=0.06 -o jobs/role5-t2-smoke --yes
```

Before accepting either smoke run, check that Harbor reports `Exceptions = 0`
and that the native mini-SWE-agent trajectory contains `leanharness_category`,
`leanharness_summary`, and `leanharness_next_step` in tool-result `extra`
fields. A R5-A+B guarded request also contains `leanharness_guarded: true`.
