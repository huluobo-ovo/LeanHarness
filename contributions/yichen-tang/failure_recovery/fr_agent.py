"""Failure detection and recovery agent for mini-swe-agent 2.4.3.

Enable it in the yaml config with `agent_class: fr_agent.FailureRecoveryAgent`.
No extra LLM calls are made. The agent only runs small shell checks in the task
container and adds a short user message before the next model call when needed.

fr_detect:  hints for timeouts, repeated failures, repeated commands, and for
            the required output still missing after a number of steps.
fr_salvage: when only a few steps (or little time) are left, ask the model to
            save its current result and submit.

All interventions are written to info.failure_recovery in the trajectory.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import shlex
import time

from minisweagent.agents.interactive import InteractiveAgent, InteractiveAgentConfig

HINT_PREFIX = "[Harness monitor]"
SUBMIT_CMD = "`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`"


class FailureRecoveryConfig(InteractiveAgentConfig):
    fr_detect: bool = True
    fr_salvage: bool = True

    # detection
    fr_repeat_window: int = 6  # look back this many steps for repeated commands
    fr_near_dup_ratio: float = 0.92  # similar command + same output also counts as a repeat
    fr_error_streak: int = 2  # steps in a row where every command failed
    fr_stall_steps: int = 8  # output still missing after this many steps
    fr_cooldown: int = 4  # min steps between two hints of the same kind
    fr_max_hints: int = 6

    # salvage
    fr_salvage_steps_left: int = 5
    fr_final_steps_left: int = 2
    fr_salvage_seconds_left: int = 150


PATH_RE = re.compile(r"(?<![\w.])(/(?:[\w.\-]+/)*[\w.\-]+)")
OUTPUT_WORDS = re.compile(r"\b(output|outputs|save|saved|write|export|deliverable)\b", re.I)
INPUT_WORDS = re.compile(r"\b(input|inputs|provided|given|source)\b", re.I)
# used only when the task does not name an output file
WRITE_RE = re.compile(
    r"(?:>>?\s*[^\s&|>]|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i|\btouch\b|\.save\(|\.write\(|"
    r"\bto_csv\b|\bto_excel\b|savefig|\bln\s|\bchmod\b|open\([^)]*['\"][wa]b?['\"]|"
    r"\bgsettings\s+set\b|\bdconf\s+write\b|\bsoffice\b|\blibreoffice\b)"
)


def normalize(cmd: str) -> str:
    return re.sub(r"\s+", " ", cmd).strip()


def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


def extract_output_paths(task: str) -> list[str]:
    """Find output file paths in the task text.

    A path is treated as an output if it is under an artifacts/output folder, or if
    the closest heading above it is about outputs (e.g. "Required final output:").
    """
    found = []
    section = None
    for line in task.splitlines():
        head = line.strip().strip("`*-# ")
        short = head.endswith(":") or len(head.split()) <= 6
        if short and OUTPUT_WORDS.search(head):
            section = "out"
        elif short and INPUT_WORDS.search(head):
            section = "in"
        for p in PATH_RE.findall(line):
            if p.endswith("/") or len(p) < 4:
                continue
            low = p.lower()
            if "/artifacts/" in low or "/output" in low:
                found.append(p)
            elif section == "out" and "." in p.rsplit("/", 1)[-1]:
                found.append(p)
    return list(dict.fromkeys(found))


class FailureRecoveryAgent(InteractiveAgent):
    def __init__(self, *args, config_class=FailureRecoveryConfig, **kwargs):
        super().__init__(*args, config_class=config_class, **kwargs)
        # wrap env.execute so we can see the outputs of each step
        self._env_execute = self.env.execute
        self.env.execute = self._execute_and_record
        self.step_outputs = []
        self.history = []  # one entry per command: step, command, output hash
        self.error_streak = 0
        self.last_write_step = 0
        self.last_hint = {}
        self.n_hints = 0
        self.salvage_done = set()
        self.output_paths = []
        self.fr_events = []

    def _execute_and_record(self, action, *args, **kwargs):
        out = self._env_execute(action, *args, **kwargs)
        self.step_outputs.append((action, out))
        return out

    def _shell(self, command: str) -> str:
        # not shown to the model and not counted as a step
        try:
            return self._env_execute({"command": command}, timeout=10).get("output", "")
        except TypeError:
            return self._env_execute({"command": command}).get("output", "")
        except Exception:
            return ""

    def missing_outputs(self) -> list[str]:
        if not self.output_paths:
            return []
        check = "; ".join(f"[ -s {shlex.quote(p)} ] || echo {shlex.quote(p)}" for p in self.output_paths)
        lines = self._shell(check).split("\n")
        return [p for p in self.output_paths if p in lines]

    def run(self, task: str = "", **kwargs) -> dict:
        self.output_paths = extract_output_paths(task)
        self.log("init", output_paths=self.output_paths)
        return super().run(task, **kwargs)

    def log(self, kind: str, **data) -> None:
        t = round(time.time() - self._start_time, 1)
        self.fr_events.append({"step": self.n_calls, "kind": kind, "t": t, **data})

    def add_hint(self, kinds: list[str], lines: list[str]) -> None:
        header = HINT_PREFIX
        if self.config.step_limit:
            left = self.config.step_limit - self.n_calls
            header += f" Step {self.n_calls}/{self.config.step_limit}, {left} model calls left."
        content = header + "\n" + "\n".join(f"- {x}" for x in lines)
        self.add_messages({"role": "user", "content": content, "extra": {"interrupt_type": "FailureRecovery", "fr_kinds": kinds}})
        self.log("hint", kinds=kinds, chars=len(content))

    def serialize(self, *extra_dicts) -> dict:
        info = {
            "fr_detect": self.config.fr_detect,
            "fr_salvage": self.config.fr_salvage,
            "n_detect_hints": self.n_hints,
            "salvage_fired": sorted(self.salvage_done),
            "injected_chars": sum(e.get("chars", 0) for e in self.fr_events),
            "events": self.fr_events,
        }
        return super().serialize({"info": {"failure_recovery": info}}, *extra_dicts)

    # salvage: checked right before each model call
    def query(self) -> dict:
        if self.config.fr_salvage:
            self.check_deadline()
        return super().query()

    def check_deadline(self) -> None:
        c = self.config
        steps_left = c.step_limit - self.n_calls if c.step_limit else 10**9
        secs_left = c.wall_time_limit_seconds - (time.time() - self._start_time) if c.wall_time_limit_seconds else 10**9
        if steps_left <= 0 or secs_left <= 0:
            return
        if steps_left <= c.fr_final_steps_left and "final" not in self.salvage_done:
            stage = "final"
        elif (steps_left <= c.fr_salvage_steps_left or secs_left <= c.fr_salvage_seconds_left) and not self.salvage_done:
            stage = "salvage"
        else:
            return
        self.salvage_done.add(stage)

        missing = self.missing_outputs()
        where = f" ({', '.join(missing)})" if missing else ""
        if self.output_paths and not missing:
            lines = [f"The required output file(s) already exist. Do at most one quick format check, then submit with {SUBMIT_CMD} on its own."]
        elif stage == "salvage":
            if secs_left <= c.fr_salvage_seconds_left:
                reason = f"only about {int(secs_left)}s of time left"
            else:
                reason = "the step budget is almost used up"
            lines = [
                f"Running out of budget ({reason}). If the run stops now, nothing is saved.",
                f"Stop exploring. In the next step, write your current best answer or make the required change{where}, "
                f"even if it is approximate. Then check it exists and submit with {SUBMIT_CMD} on its own.",
            ]
        else:
            lines = [
                f"Last call or two before the run is stopped. If the result is not saved yet{where}, save it in this step "
                f"with your best estimate. Otherwise submit now with {SUBMIT_CMD} on its own."
            ]
        self.add_hint([stage], lines)

    # detection: checked after the commands of each step have run
    def execute_actions(self, message: dict) -> list[dict]:
        self.step_outputs = []
        result = super().execute_actions(message)
        if self.config.fr_detect:
            self.detect(message)
        return result

    def detect(self, message: dict) -> None:
        c = self.config
        step = self.n_calls
        outs = self.step_outputs
        hints = {}

        if any((o.get("extra") or {}).get("exception_type") == "TimeoutExpired" for _, o in outs):
            hints["timeout"] = (
                "A command hit the time limit and was killed. Do not run it again unchanged. Run long jobs in the "
                "background (`nohup CMD > /tmp/job.log 2>&1 &`, then `tail /tmp/job.log`) or reduce the work "
                "(fewer files, smaller input, simpler method)."
            )

        all_failed = bool(outs) and all(o.get("returncode", 0) != 0 or o.get("exception_info") for _, o in outs)
        self.error_streak = self.error_streak + 1 if all_failed else 0
        if self.error_streak >= c.fr_error_streak and "timeout" not in hints:
            hints["errors"] = (
                f"The last {self.error_streak} steps all failed. Read the error message and try a different approach "
                "instead of small edits to the same command. Check the tool, module or path exists (`which`, `ls`, "
                "`--help`), or use a simpler tool. Ignore this if the non-zero exit was expected (e.g. grep with no match)."
            )

        recent = [h for h in self.history if 0 < step - h["step"] <= c.fr_repeat_window]
        repeat_of = None
        for action, out in outs:
            cmd = normalize(action.get("command", ""))
            h_out = md5(out.get("output", ""))
            for h in recent:
                if h["cmd"] == cmd or (
                    h["out"] == h_out and difflib.SequenceMatcher(None, h["cmd"], cmd).ratio() >= c.fr_near_dup_ratio
                ):
                    repeat_of = h["step"]
                    break
            self.history.append({"step": step, "cmd": cmd, "out": h_out})
            raw = re.sub(r"\d?>\s*/dev/null|\d?>&\d", "", action.get("command", ""))
            if WRITE_RE.search(raw):
                self.last_write_step = step
        if repeat_of is not None:
            hints["repeat"] = (
                f"This repeats what you did at step {repeat_of} and gives the same result. "
                "Use what you already know or try a different method."
            )

        # near the end the salvage message takes over
        salvage_soon = c.fr_salvage and c.step_limit and c.step_limit - step <= c.fr_salvage_steps_left
        if step >= c.fr_stall_steps and not salvage_soon:
            if self.output_paths:
                missing = self.missing_outputs()
                if missing:
                    hints["stall"] = (
                        f"After {step} steps, {', '.join(missing)} still does not exist. Write a first version now with "
                        "your current best result and improve it later if there is budget left. No file means zero score."
                    )
            elif step - self.last_write_step >= c.fr_stall_steps:
                hints["stall"] = (
                    f"Nothing has been changed for {step - self.last_write_step} steps. "
                    "Stop investigating and make the change the task asks for, then verify it."
                )

        if not hints:
            return
        ready = {k: v for k, v in hints.items() if step - self.last_hint.get(k, -10**9) >= c.fr_cooldown}
        if not ready or self.n_hints >= c.fr_max_hints:
            self.log("suppressed", kinds=list(hints))
            return
        for k in ready:
            self.last_hint[k] = step
        self.n_hints += 1
        self.add_hint(list(ready), list(ready.values()))
