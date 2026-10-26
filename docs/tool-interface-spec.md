# LeanHarness v1 Tool Interface Specification

**Owner:** Tool-interface workstream (Role 5)  
**Status:** Design ready for implementation; no benchmark integration yet  
**Companion document:** [`tool-interface-map.md`](tool-interface-map.md)

## 1. Purpose

The mini-SWE-agent baseline exposes a single tool: `bash(command)`. LeanHarness v1 keeps that tool unchanged from the model's perspective and adds two optional harness layers around it:

1. **Command Guard:** blocks only clearly malformed requests before an environment call.
2. **Result Normalizer:** converts raw command outcomes into concise, structured, actionable feedback after execution.

The goal is to reduce wasted turns caused by empty commands and hard-to-interpret shell failures without changing the model, benchmark tasks, official verifier, or per-task budgets.

## 2. Non-goals

LeanHarness v1 does **not**:

- decide whether a shell command is safe, desirable, or likely to solve a task;
- infer a correct path, silently repair a command, or execute a replacement command;
- remove the baseline `bash` tool or add a read/write/search/edit tool suite;
- inspect official verifier tests or task solutions;
- suppress raw output from the saved trajectory;
- change model, decoding settings, step limit, time limit, or cost cap.

These limits make the v1 intervention narrow enough for an interpretable ablation.

## 3. Data flow

```text
model tool call: bash(command)
            |
            v
     existing parser
            |
            v
   Command Guard (optional)
     |                 |
 valid action      synthetic failure result
     |                 |
     v                 |
baseline env.execute(action)
            |
            v
 Result Normalizer (optional)
            |
            v
baseline observation formatter
            |
            v
next model message + persisted trajectory
```

The wrapper must preserve the baseline action/result shape so the existing mini-SWE-agent observation formatter and the final Harbor adapter can consume it.

## 4. Public configuration

The v1 configuration uses independent flags to support a clean component ablation.

```yaml
harness:
  tool_interface:
    guard_enabled: false
    normalizer_enabled: false
    max_command_chars: 12000
    summary_max_chars: 600
    raw_tail_max_chars: 3000
```

| Field | Meaning | Baseline value |
| --- | --- | --- |
| `guard_enabled` | Apply pre-execution malformed-command checks. | `false` |
| `normalizer_enabled` | Add structured diagnostic fields after each environment result. | `false` |
| `max_command_chars` | Maximum command length accepted by the v1 guard. | `12000` |
| `summary_max_chars` | Upper bound for the model-facing diagnostic summary. | `600` |
| `raw_tail_max_chars` | Maximum raw-output tail copied into the concise model-facing feedback. The full raw output remains in the trajectory. | `3000` |

Any threshold modified after development must be recorded in the run configuration and experiment table.

## 5. Command Guard contract

### Function signature

```python
def validate_action(action: dict, *, max_command_chars: int) -> GuardDecision: ...
```

Suggested result type:

```python
@dataclass
class GuardDecision:
    should_execute: bool
    action: dict
    category: str | None = None
    summary: str | None = None
    next_step: str | None = None
```

### Inputs and outputs

The baseline parser normally yields:

```python
{"command": "ls -la", "tool_call_id": "call_abc"}
```

For a valid action, `should_execute=True` and `action` is passed to the original `env.execute(action)` unchanged.

For a blocked malformed action, no shell command is run. The wrapper produces a synthetic environment-like result:

```python
{
    "output": "",
    "returncode": 2,
    "exception_info": "LeanHarness rejected a malformed tool request before execution.",
    "extra": {
        "leanharness_guarded": True,
        "leanharness_category": "empty_command",
        "leanharness_summary": "The bash command is empty, so nothing was executed.",
        "leanharness_next_step": "Provide one concrete shell command."
    }
}
```

The original `tool_call_id` remains on the action so the normal mini-SWE-agent formatter preserves tool-call correlation.

### v1 checks

| Rule | Condition | Execute? | Category | Model-facing summary | Suggested next step |
| --- | --- | ---:| --- | --- | --- |
| Missing command | `command` absent or not a string | No | `missing_command` | The bash request has no string `command` argument. | Provide one concrete shell command. |
| Empty command | `command.strip() == ""` | No | `empty_command` | The bash command is empty, so nothing was executed. | Provide one concrete shell command. |
| Excessively long command | `len(command) > max_command_chars` | No | `command_too_long` | The command exceeds the configured length limit and was not executed. | Split the work into smaller commands. |
| All other commands | Any non-empty command within the length limit | Yes | — | — | — |

The guard intentionally does **not** block shell metacharacters, `rm`, network commands, root-like commands, or commands expected to fail. Project 5 evaluates task performance, not a security approval policy.

## 6. Result Normalizer contract

### Function signature

```python
def normalize_result(
    result: dict,
    *,
    summary_max_chars: int,
    raw_tail_max_chars: int,
) -> dict: ...
```

The function returns a copy of the execution result with all original fields preserved and these optional fields added under `extra`:

```python
{
    "extra": {
        "leanharness_category": "file_not_found",
        "leanharness_summary": "The referenced path does not exist.",
        "leanharness_next_step": "List or search the directory before retrying that path.",
        "leanharness_raw_tail": "cat: src/mian.py: No such file or directory"
    }
}
```

`output`, `returncode`, `exception_info`, and any existing `extra` fields must never be overwritten. `leanharness_raw_tail` is only a compact convenience copy; the complete original output remains available in `raw_output` after the baseline formatter serializes the trajectory.

### v1 outcome taxonomy

Classification is deterministic and uses only the command result; it does not make another model call.

| Category | Priority rule | Summary | Suggested next step |
| --- | --- | --- | --- |
| `guarded_request` | `extra.leanharness_guarded == True` | Use the guard-generated summary. | Use the guard-generated next step. |
| `timeout_or_exception` | `exception_info` is non-empty | The command could not complete because the execution layer reported an exception or timeout. | Try a smaller, bounded command and inspect the error details. |
| `success` | `returncode == 0` | Command completed with exit code 0. | Inspect output and continue with the task. |
| `file_not_found` | non-zero return code and output contains `No such file or directory` | The referenced path does not exist. | List or search the directory before retrying that path. |
| `command_not_found` | non-zero return code and output contains `command not found` | The requested command is unavailable or misspelled. | Check the command name or use an installed alternative. |
| `permission_denied` | non-zero return code and output contains `Permission denied` | The command lacks permission for the target. | Inspect permissions and target path before retrying. |
| `other_failure` | non-zero return code not matched above | Command failed with a non-zero exit code. | Read the key error lines and choose a different diagnostic or repair step. |

Matching should be case-insensitive. The recorded category is a hint for the next action, not a claim of ground truth.

### Model-facing rendering

When `normalizer_enabled=True`, the observation template should add this bounded block ahead of the existing raw result rendering:

```text
<leanharness_feedback>
category: {{ output.extra.leanharness_category }}
summary: {{ output.extra.leanharness_summary }}
suggested_next_step: {{ output.extra.leanharness_next_step }}
</leanharness_feedback>
```

The existing baseline fields must remain visible:

```text
<returncode>...</returncode>
<output>...</output>
```

If the normalizer is disabled, no extra feedback block is rendered. This preserves C0 behaviour.

## 7. Experiment configurations

The v1 plan fits the project limit of at most three configurations per individual scheme.

| Config ID | Guard | Normalizer | Purpose |
| --- | ---:| ---:| --- |
| C0 | Off | Off | Shared default-harness baseline, run by Role 1. |
| T1 | Off | On | Isolate whether clearer error feedback changes success/cost. |
| T2 | On | On | Test the complete Role 5 v1. |

All configurations must use the same base model, task list, seed policy, step limit, wall-time limit, cost cap, Harbor adapter, and official verifier. T1/T2 results must record the LeanHarness code commit and configuration file.

## 8. Acceptance checks before paid benchmark runs

The implementation is ready for the fixed development subset only after it passes these no-cost unit tests:

1. Valid `bash` action reaches a fake environment unchanged.
2. Missing, empty, and too-long commands do not reach the fake environment.
3. Every guard rejection yields an environment-like result with a non-zero return code.
4. Result normalization preserves existing `output`, `returncode`, `exception_info`, and `extra` keys.
5. Each named category maps to the expected summary and suggested next step.
6. An unknown non-zero failure maps to `other_failure`, not an invented specific diagnosis.
7. Tool-result formatting retains the originating `tool_call_id`.
8. With both flags off, output equals baseline behaviour.

## 9. Implementation hand-off

Planned code layout after the shared adapter is available:

```text
src/leanharness/tools/
  guard.py        # validate_action and synthetic-result helper
  normalizer.py   # normalize_result and classification helpers
  wrapper.py      # thin execution wrapper; no benchmark-specific logic
tests/
  test_tool_interface.py
configs/
  tool-interface-normalizer.yaml
  tool-interface-complete.yaml
```

The final location may be adjusted to match Role 1's adapter layout, but the public contracts and configuration names above should remain stable.
