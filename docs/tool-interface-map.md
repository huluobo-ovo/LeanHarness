# Mini-SWE-agent Tool Interface Map

**Owner:** Tool-interface workstream (Role 5)  
**Upstream inspected:** `SWE-agent/mini-swe-agent` at `04d809ceab9df28f9adaed044884180159172930`  
**Scope:** The default OpenRouter chat-completions path using tool calls. This is the intended LeanHarness baseline path unless the team deliberately chooses the Responses API or text-action adapter.

## Why this map exists

LeanHarness will compare harness changes fairly. Before changing the tool interface, we need a precise map of where a model action is created, parsed, executed, and returned to the model. The first tool-interface variant should wrap these existing boundaries rather than rewrite the agent loop or modify the official TUA-Bench verifier.

## Baseline command round trip

```text
Task prompt + previous messages
        |
        v
DefaultAgent.query()
        |
        v
OpenRouterModel.query(messages)
  - sends one declared tool: bash(command: string)
        |
        v
parse_toolcall_actions()
  - validates tool name and JSON arguments
  - creates action dictionaries
        |
        v
DefaultAgent.execute_actions(message)
        |
        v
Environment.execute(action)
  - runs command in the task environment / container
  - returns output, returncode, exception_info
        |
        v
format_toolcall_observation_messages()
  - creates a tool-result message
        |
        v
DefaultAgent.add_messages(...)
        |
        +----> the next model call sees the command result in its history
```

## Source-code map

| Stage | File | Symbol | Actual responsibility | Role 5 relevance |
| --- | --- | --- | --- | --- |
| Agent loop | `src/minisweagent/agents/default.py` | `DefaultAgent.run()` / `step()` | Initializes system and task messages, repeats model-query then action-execution steps, writes the trajectory. | Do not replace this loop in the first variant. It is the stable orchestration point. |
| Budget gate and model call | `src/minisweagent/agents/default.py` | `DefaultAgent.query()` | Enforces step/cost/time limits, calls `self.model.query(self.messages)`, adds the returned assistant message, and accumulates its cost. | Keep this unchanged so all variants retain the same agent budget semantics. |
| Action execution boundary | `src/minisweagent/agents/default.py` | `DefaultAgent.execute_actions()` | Iterates through `message["extra"]["actions"]`, calls `self.env.execute(action)`, then asks the model adapter to format observations. | **Primary integration boundary.** A wrapper here can validate actions before execution and normalize outputs afterwards. |
| Declared default tool | `src/minisweagent/models/utils/actions_toolcall.py` | `BASH_TOOL` | Defines the only default tool: `bash` with required string argument `command`. | Add structured tools only after the lightweight variant is validated; changing this schema changes the model-facing interface. |
| Tool-call parser | `src/minisweagent/models/utils/actions_toolcall.py` | `parse_toolcall_actions()` | Rejects missing tool calls, unknown tools, invalid JSON, or missing `command`; emits action dictionaries with `command` and `tool_call_id`. | Existing parser already handles syntax-level validation. Role 5 should add semantic validation, such as empty commands or invalid paths, without duplicating parser logic. |
| OpenRouter model adapter | `src/minisweagent/models/openrouter_model.py` | `OpenRouterModel._query()` / `query()` / `_parse_actions()` | Sends messages and `BASH_TOOL` to OpenRouter, asks for usage, records cost, then calls the tool-call parser. | Retain this for unified API use and cost accounting. Do not put task-specific logic in the provider adapter. |
| Docker command execution | `src/minisweagent/environments/docker.py` | `DockerEnvironment.execute()` | Executes `bash -lc <command>` in the running container and returns `{output, returncode, exception_info}`; converts execution exceptions to structured output. | Preserve raw execution behaviour. Wrap the environment or normalize the returned dictionary; do not hide raw output from trajectory logs. |
| Result-to-message conversion | `src/minisweagent/models/utils/actions_toolcall.py` | `format_toolcall_observation_messages()` | Renders the execution result into a `role="tool"` message, preserves `raw_output`, `returncode`, `exception_info`, timestamp, and tool-call ID in `extra`. | **Primary feedback boundary.** Add a concise, structured diagnosis for the model while retaining raw details in `extra`. |
| Text-action alternative | `src/minisweagent/models/utils/actions_text.py` | `parse_regex_actions()` / `format_observation_messages()` | Legacy path: extracts exactly one command from a text block and returns result as a user message. | Not the first target. If the team uses this adapter, mirror the same wrapper policy and tests. |

## Data contracts to preserve

### Parsed action

The default path expects an action dictionary like:

```python
{"command": "ls -la", "tool_call_id": "call_..."}
```

`tool_call_id` must survive to the corresponding tool-result message for tool-call API compatibility.

### Execution result

The environment returns a dictionary shaped like:

```python
{
    "output": "combined stdout/stderr text",
    "returncode": 0,
    "exception_info": "",
}
```

For infrastructure exceptions it uses `returncode=-1`, sets `exception_info`, and may include an `extra` dictionary. The LeanHarness wrapper must retain these raw fields, even if it also adds a short diagnosis.

### Observation message

The default OpenRouter adapter emits a `role="tool"` message containing rendered output and an `extra` object with at least:

```text
raw_output, returncode, timestamp, exception_info, tool_call_id
```

This message is appended to `DefaultAgent.messages` and becomes context for the next model call.

## Recommended LeanHarness v1: guard + feedback wrapper

The first Role 5 experiment should not replace shell access. It should retain the baseline `bash` tool and insert two small, independently switchable components.

```text
parsed action
   |
   +--> ToolRequestGuard (optional)
   |       - reject empty/whitespace-only command
   |       - return a clear pre-execution message for invalid wrapper arguments
   |
   v
original env.execute(action)
   |
   v
ToolFeedbackNormalizer (optional)
   - classify common outcomes from returncode/output/exception_info
   - keep concise signal for the model
   - preserve raw output in the saved trajectory
```

### Candidate output categories

| Category | Example signal | Suggested model-facing guidance |
| --- | --- | --- |
| `success` | return code 0 | State that the command completed; preserve output. |
| `file_not_found` | `No such file or directory` | Search or list the directory before retrying the exact path. |
| `command_not_found` | `command not found` | Check spelling, availability, or use an installed alternative. |
| `permission_denied` | `Permission denied` | Inspect permissions/ownership; do not repeat blindly. |
| `timeout_or_exception` | `exception_info` is non-empty | State the infrastructure failure and ask for a bounded alternative. |
| `other_failure` | non-zero return code without known marker | Return exit code plus the most informative error lines. |

This classification is advice, not an auto-deny policy: normal shell failures can be useful exploration. The wrapper should not block a command merely because it contains shell syntax or might fail.

## Planned implementation points

1. Create a small `ToolRequestGuard` with pure functions that receive an action and either return it unchanged or a synthetic structured failure.
2. Create a small `ToolFeedbackNormalizer` with pure functions that receive an environment result and return the same raw result plus optional fields such as `leanharness_category` and `leanharness_summary`.
3. Add a thin environment wrapper or a `DefaultAgent.execute_actions()` subclass/override that applies the guard before, and normalizer after, the original environment call.
4. Update the observation template or formatter so the model sees the short summary, while logs retain untruncated raw output.
5. Gate both components with configuration flags. The baseline must leave them off.

## Out of scope for v1

- Replacing the official TUA-Bench verifier or reading its hidden tests.
- Rewriting `DefaultAgent.run()` or changing global step/time/cost limits.
- Replacing `bash` with a large read/write/search/edit tool suite before a lightweight ablation is working.
- Treating ordinary non-zero shell exits as automatically unsafe or unrecoverable.

## Risks and checks before formal runs

| Risk | Required check |
| --- | --- |
| Breaking tool-call correlation | Each tool-result message keeps the originating `tool_call_id`. |
| Hiding useful diagnostics | Raw command output remains in `extra.raw_output` and the serialized trajectory. |
| Accidentally changing budgets | Same model, decoding settings, task list, time/step/cost cap as C0. |
| Prompt cost increases | Count any extra model tokens introduced by summaries/templates and report them. |
| Overfitting error patterns | Use the fixed development subset first, then the frozen 40-task evaluation subset. |
| Adapter mismatch | Run a one-task smoke test through the final Harbor adapter before any paid batch run. |

## Hand-off to Role 1

When the shared Harbor adapter is ready, Role 5 needs one confirmed integration point: either an environment object conforming to `Environment.execute(action)`, or a subclassable `DefaultAgent.execute_actions()` boundary. The adapter should preserve the mini-SWE-agent action/result contracts above and expose the serialized trajectory path so structured feedback can be audited.
