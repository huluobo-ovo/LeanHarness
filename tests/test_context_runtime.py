"""Offline contract tests for Scheme A's mini-SWE context boundary."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "contributions/liu-yalin/developer_pack/examples/c0_single_task/000-count-nuclei__hZaqcvy/agent/mini-swe-agent.trajectory.json"


def load_runtime():
    package = types.ModuleType("minisweagent")
    agents = types.ModuleType("minisweagent.agents")
    default = types.ModuleType("minisweagent.agents.default")

    class AgentConfig(BaseModel):
        pass

    class DefaultAgent:
        def __init__(self, model, env, *, config_class=AgentConfig, **kwargs):
            self.model = model
            self.env = env
            self.config = config_class(**kwargs)

    default.AgentConfig = AgentConfig
    default.DefaultAgent = DefaultAgent
    saved = {name: sys.modules.get(name) for name in ("minisweagent", "minisweagent.agents", "minisweagent.agents.default")}
    sys.modules.update({"minisweagent": package, "minisweagent.agents": agents, "minisweagent.agents.default": default})
    try:
        spec = importlib.util.spec_from_file_location("leanharness_context_test_runtime", ROOT / "adapters/context_runtime_agent.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


RUNTIME = load_runtime()


def observation(call_id: str, raw: str, *, returncode: int = 0, exception_info: str | None = None):
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps({"returncode": returncode, "output": raw}, ensure_ascii=False),
        "extra": {"raw_output": raw, "returncode": returncode, "exception_info": exception_info},
    }


def history(groups: int, raw: str = "x" * 1000):
    messages = [{"role": "system", "content": "system"}, {"role": "user", "content": "task"}]
    for index in range(1, groups + 1):
        call_id = f"call-{index}"
        messages.extend([
            {"role": "assistant", "content": f"step {index}", "tool_calls": [{"id": call_id, "function": {"name": "bash"}}]},
            observation(call_id, raw),
        ])
    return messages


class SpyModel:
    def __init__(self):
        self.requests = []

    def query(self, messages, **kwargs):
        self.requests.append(copy.deepcopy(messages))
        return {"role": "assistant", "content": "next", "extra": {"cost": 0.01}}

    def format_observation_messages(self, message, outputs, template_vars=None):
        return outputs

    def get_template_vars(self):
        return {}

    def serialize(self):
        return {}


class ContextRuntimeTests(unittest.TestCase):
    def test_disabled_proxy_preserves_model_visible_c0_request(self):
        messages = history(12)
        direct = SpyModel()
        direct.query(messages)
        wrapped = SpyModel()
        RUNTIME.ContextModelProxy(wrapped, RUNTIME.ContextSettings()).query(messages)
        self.assertEqual(wrapped.requests[0], direct.requests[0])

    def test_a_threshold_unicode_failure_and_raw_evidence(self):
        settings = RUNTIME.ContextSettings(output_shaping_enabled=True)
        short = observation("short", "\u754c" * 3000)
        long_raw = "\u9996" * 1000 + "\nERROR concrete failure\n" + "\u4e2d" * 1800 + "\u5c3e" * 1000
        long = observation("long", long_raw, returncode=7, exception_info="command failed")
        before = copy.deepcopy([short, long])
        shaped = RUNTIME.shape_observations([short, long], settings)
        self.assertIs(shaped[0], short)
        self.assertEqual(shaped[0], before[0])
        self.assertLessEqual(len(shaped[1]["content"]), 3000)
        payload = json.loads(shaped[1]["content"])
        self.assertEqual(payload["returncode"], 7)
        self.assertIn("ERROR concrete failure", payload["middle_diagnostics"])
        self.assertIn("command failed", payload["exception_info"])
        self.assertEqual(shaped[1]["tool_call_id"], "long")
        self.assertEqual(shaped[1]["extra"]["raw_output"], long_raw)
        self.assertEqual(long, before[1])

    def test_a_never_shapes_non_tool_messages(self):
        message = {"role": "user", "content": "keep", "extra": {"raw_output": "x" * 4000}}
        self.assertIs(RUNTIME.shape_observations([message], RUNTIME.ContextSettings(output_shaping_enabled=True))[0], message)

    def test_a_minimum_allowed_limit_keeps_exception_signal(self):
        settings = RUNTIME.ContextSettings(output_shaping_enabled=True, output_char_limit=512)
        long = observation("one", "x" * 1000 + "\nERROR detail\n" + "y" * 1000, returncode=7, exception_info="exception text " * 20)
        shaped = RUNTIME.shape_observations([long], settings)[0]
        payload = json.loads(shaped["content"])
        self.assertLessEqual(len(shaped["content"]), 512)
        self.assertEqual(payload["returncode"], 7)
        self.assertIn("exception text", payload["exception_info"])

    def test_b_batch_boundaries_and_durable_history(self):
        settings = RUNTIME.ContextSettings(history_compaction_enabled=True)
        for count, expected in ((11, 0), (12, 6), (17, 6), (18, 12)):
            with self.subTest(count=count):
                original = history(count)
                snapshot = copy.deepcopy(original)
                projected, stats = RUNTIME.project_history(original, settings)
                self.assertEqual(stats["folded_groups"], expected)
                self.assertEqual(stats["folded_observations"], expected)
                self.assertEqual(original, snapshot)
                self.assertEqual(len(projected), len(original))
                for index, message in enumerate(original):
                    self.assertEqual(projected[index].get("tool_call_id"), message.get("tool_call_id"))
                    self.assertEqual(projected[index].get("tool_calls"), message.get("tool_calls"))
                self.assertEqual(projected[-1], original[-1])

    def test_b_skips_format_errors_and_bad_tool_ids(self):
        messages = history(12)
        messages[4:4] = [{"role": "assistant", "content": "format error"}, {"role": "user", "content": "retry format"}]
        settings = RUNTIME.ContextSettings(history_compaction_enabled=True)
        _, stats = RUNTIME.project_history(messages, settings)
        self.assertEqual(stats["folded_groups"], 6)
        malformed = history(12)
        malformed[2]["tool_calls"] = [{"id": "duplicate"}, {"id": "duplicate"}]
        _, stats = RUNTIME.project_history(malformed, settings)
        self.assertEqual(stats["folded_groups"], 0)
        missing = history(12)
        missing[3]["tool_call_id"] = None
        _, stats = RUNTIME.project_history(missing, settings)
        self.assertEqual(stats["folded_groups"], 0)

    def test_b_keeps_multiple_tool_results_paired(self):
        messages = history(12)
        messages[2]["tool_calls"].append({"id": "second", "function": {"name": "bash"}})
        messages.insert(4, observation("second", "y" * 1000))
        projected, stats = RUNTIME.project_history(messages, RUNTIME.ContextSettings(history_compaction_enabled=True))
        self.assertEqual(stats["folded_groups"], 6)
        self.assertEqual(stats["folded_observations"], 7)
        self.assertEqual(projected[4]["tool_call_id"], "second")
        self.assertEqual(messages[4]["extra"]["raw_output"], "y" * 1000)

    def test_proxy_logs_request_projection_without_mutation(self):
        messages = history(12)
        original = copy.deepcopy(messages)
        spy = SpyModel()
        response = RUNTIME.ContextModelProxy(spy, RUNTIME.ContextSettings(history_compaction_enabled=True)).query(messages)
        metadata = response["extra"]["context_history"]
        self.assertEqual(metadata["folded_groups"], 6)
        self.assertLess(metadata["request_chars_after"], metadata["request_chars_before"])
        self.assertEqual(len(metadata["request_sha256"]), 64)
        self.assertEqual(messages, original)
        self.assertEqual(spy.requests[0][0], messages[0])
        self.assertEqual(spy.requests[0][1], messages[1])

    def test_agent_selects_context_settings(self):
        agent = RUNTIME.ContextDefaultAgent(SpyModel(), object(), context_management={"output_shaping_enabled": True})
        self.assertTrue(agent.config.context_management.output_shaping_enabled)
        self.assertIsInstance(agent.model, RUNTIME.ContextModelProxy)

    def test_offline_replay_accepts_real_c0_message_structure(self):
        original = json.loads(SAMPLE.read_text())["messages"]
        last_assistant = max(index for index, message in enumerate(original) if message.get("role") == "assistant")
        prefix = original[:last_assistant]
        snapshot = copy.deepcopy(prefix)
        settings = RUNTIME.ContextSettings(output_shaping_enabled=True, history_compaction_enabled=True)
        shaped = RUNTIME.shape_observations(prefix, settings)
        projected, stats = RUNTIME.project_history(shaped, settings)
        self.assertGreater(sum(bool((message.get("extra") or {}).get("context_output_shaped")) for message in shaped), 0)
        self.assertGreater(stats["folded_observations"], 0)
        self.assertEqual(len(projected), len(prefix))
        self.assertEqual(prefix, snapshot)
        self.assertEqual([message.get("tool_call_id") for message in projected], [message.get("tool_call_id") for message in prefix])


if __name__ == "__main__":
    unittest.main()
