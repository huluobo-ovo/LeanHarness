import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("minisweagent")

from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models.test_models import (
    DeterministicModel,
    DeterministicToolcallModel,
    make_output,
    make_toolcall_output,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fr_agent import FailureRecoveryAgent, extract_output_paths  # noqa: E402

BASE = dict(
    system_template="sys",
    instance_template="{{task}}",
    step_limit=30,
    cost_limit=0,
    wall_time_limit_seconds=900,
    mode="yolo",
    confirm_exit=False,
)


def make_task(out_path):
    return f"""Use the provided microscopy images to count how many nuclei are present.

Inputs:
- `/app/input/images/1-162hrh2ax2.tif`

Required final output:
- `{out_path}`

Write only the integer nuclei/cell count in the output file.
"""


def explore(i):
    return make_output(f"look {i}", [{"command": f"echo exploring step {i}"}])


def run(task, outputs, toolcall=False, timeout=30, **cfg):
    model_cls = DeterministicToolcallModel if toolcall else DeterministicModel
    agent = FailureRecoveryAgent(model_cls(outputs=outputs), LocalEnvironment(timeout=timeout), **{**BASE, **cfg})
    return agent, agent.run(task)


def hints(agent):
    return [(e["step"], e["kinds"]) for e in agent.fr_events if e["kind"] == "hint"]


@pytest.fixture
def out_file(tmp_path):
    return str(tmp_path / "app" / "artifacts" / "nuclei_count.txt")


def test_extract_output_paths(out_file):
    assert extract_output_paths(make_task(out_file)) == [out_file]
    assert extract_output_paths("Edit the file nuclei/cell then save.") == []


def test_stall_and_salvage(out_file):
    agent, res = run(make_task(out_file), [explore(i) for i in range(1, 31)])
    h = hints(agent)
    assert res["exit_status"] == "LimitsExceeded"
    assert (8, ["stall"]) in h
    assert (25, ["salvage"]) in h
    assert (28, ["final"]) in h
    assert not any(s >= 25 and k == ["stall"] for s, k in h)
    assert agent.n_hints <= agent.config.fr_max_hints


def test_agent_saves_after_salvage(out_file):
    outputs = [explore(i) for i in range(1, 26)]
    outputs.append(make_output("write", [{"command": f"mkdir -p {Path(out_file).parent} && echo 42 > {out_file}"}]))
    outputs.append(make_output("submit", [{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}]))
    agent, res = run(make_task(out_file), outputs)
    assert res["exit_status"] == "Submitted"
    assert Path(out_file).read_text().strip() == "42"
    assert "failure_recovery" in agent.serialize()["info"]


def test_errors_repeat_timeout(out_file):
    outputs = [
        make_output("a", [{"command": "ls /definitely/missing"}]),
        make_output("b", [{"command": "ls   /definitely/missing"}]),
        make_output("c", [{"command": "cat /also/missing"}]),
        make_output("d", [{"command": "sleep 3"}]),
        make_output("e", [{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}]),
    ]
    agent, _ = run(make_task(out_file), outputs, timeout=1)
    h = hints(agent)
    assert any(s == 2 and "repeat" in k and "errors" in k for s, k in h)
    assert any(s == 4 and "timeout" in k for s, k in h)
    assert not any(s == 3 and "errors" in k for s, k in h)


def test_ablation_has_no_salvage(out_file):
    agent, _ = run(make_task(out_file), [explore(i) for i in range(1, 31)], fr_salvage=False)
    h = hints(agent)
    assert not any(k in (["salvage"], ["final"]) for _, k in h)
    assert any(k == ["stall"] for _, k in h)


def test_both_off_matches_vanilla(out_file):
    task = make_task(out_file)
    agent, res = run(task, [explore(i) for i in range(1, 31)], fr_detect=False, fr_salvage=False)
    vanilla = InteractiveAgent(DeterministicModel(outputs=[explore(i) for i in range(1, 31)]), LocalEnvironment(), **BASE)
    vres = vanilla.run(task)
    assert hints(agent) == []
    assert len(agent.messages) == len(vanilla.messages)
    assert res["exit_status"] == vres["exit_status"]


def test_toolcall_message_order(out_file):
    def tc(i):
        cmd = f"echo hi {i}"
        call = {"id": f"call_{i}", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": cmd})}}
        return make_toolcall_output(None, [call], [{"command": cmd, "tool_call_id": f"call_{i}"}])

    agent, _ = run(make_task(out_file), [tc(i) for i in range(1, 31)], toolcall=True)
    for i, m in enumerate(agent.messages):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            assert agent.messages[i + 1]["role"] == "tool"
    assert any(str(m.get("content", "")).startswith("[Harness monitor]") for m in agent.messages if m.get("role") == "user")
