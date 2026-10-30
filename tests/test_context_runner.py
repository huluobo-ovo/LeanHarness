"""Offline checks for Scheme A's command and raw-result accounting."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_context_batch.py"
SPEC = importlib.util.spec_from_file_location("run_context_batch_test", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
SAMPLE = ROOT / "contributions/liu-yalin/developer_pack/examples/c0_single_task/000-count-nuclei__hZaqcvy/agent/mini-swe-agent.trajectory.json"


class ContextRunnerTests(unittest.TestCase):
    def test_c0_and_b_commands_share_all_noncontext_args(self):
        args = argparse.Namespace(uv="uv", model="openrouter/example/model", cost_limit=0.06, configuration="C0")
        c0 = RUNNER.command_for(args, "000-count-nuclei", "trial", Path("trials"))
        args.configuration = "B"
        ab = RUNNER.command_for(args, "000-count-nuclei", "trial", Path("trials"))
        self.assertEqual(ab[:-2], c0)
        self.assertNotIn("context_config_file", " ".join(c0))
        self.assertTrue(ab[-1].startswith("context_config_file="))

    def test_known_sample_reports_real_response_usage_not_zero_harbor_cost(self):
        measured = RUNNER.trajectory_metrics(SAMPLE)
        self.assertEqual(measured["cost_status"], "complete")
        self.assertEqual(measured["steps"], 30)
        self.assertEqual(measured["agent_tokens_in"], 476067)
        self.assertEqual(measured["agent_tokens_out"], 17533)
        self.assertAlmostEqual(measured["agent_usd"], 0.01626169, places=8)
        self.assertEqual(measured["harness_usd"], 0.0)

    def test_missing_or_zero_usage_is_not_recorded_as_free(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.json"
            path.write_text(json.dumps({"messages": [{"role": "assistant", "extra": {"response": {"usage": {"prompt_tokens": 10, "completion_tokens": 2}}}}]}))
            measured = RUNNER.trajectory_metrics(path)
            self.assertNotEqual(measured["cost_status"], "complete")
            self.assertNotIn("agent_usd", measured)
            path.write_text(json.dumps({"messages": [{"role": "assistant", "extra": {"response": "unserializable provider response"}}]}))
            measured = RUNNER.trajectory_metrics(path)
            self.assertNotEqual(measured["cost_status"], "complete")
            self.assertNotIn("agent_usd", measured)
            path.write_text(json.dumps({"messages": [{"role": "assistant", "extra": {"response": {"usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": -0.1}}}}]}))
            measured = RUNNER.trajectory_metrics(path)
            self.assertNotEqual(measured["cost_status"], "complete")
            self.assertNotIn("agent_usd", measured)
            path.write_text(json.dumps({"messages": [{"role": "assistant", "extra": {"response": {"usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0}}}}]}))
            measured = RUNNER.trajectory_metrics(path)
            self.assertNotEqual(measured["cost_status"], "complete")
            self.assertNotIn("agent_usd", measured)

    def test_dry_run_creates_no_trial_or_result(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            command = [
                sys.executable, "-B", str(SCRIPT), "--configuration", "B", "--suite", "smoke",
                "--tua-root", str(ROOT), "--model", "openrouter/example/model",
                "--task", "000-count-nuclei", "--run-root", str(temp / "runs"),
                "--record-root", str(temp / "results"),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("context_config_file=", completed.stdout)
            self.assertFalse((temp / "runs").exists())
            self.assertFalse((temp / "results").exists())

    def test_heartbeat_keeps_subprocess_output_in_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "launcher.log"
            terminal = io.StringIO()
            command = [sys.executable, "-B", "-c", "import time; print('trial output', flush=True); time.sleep(0.25)"]
            with contextlib.redirect_stdout(terminal):
                code = RUNNER.run_with_heartbeat(command, Path(directory), log_path, 0.05, "smoke-task")
            self.assertEqual(code, 0)
            self.assertIn("still running", terminal.getvalue())
            self.assertIn("trial output", log_path.read_text())

    def test_resume_skips_only_matching_completed_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            args = argparse.Namespace(run_root=temp / "runs", suite="formal", configuration="B",
                                      model="openrouter/example/model", tua_root=ROOT, cost_limit=0.06,
                                      resume=True, retry_infrastructure=False)
            task = "000-count-nuclei"
            task_root = args.run_root / args.suite / args.configuration / task
            trial = task_root / "trial-1"
            trial.mkdir(parents=True)
            trajectory = trial / "trajectory.json"
            trajectory.write_text("{}")
            manifest_path = task_root / "trial-1.manifest.json"
            manifest = {
                "suite": args.suite, "configuration": args.configuration, "task_id": task,
                "model": args.model, "source_commit": RUNNER.source_commit(),
                "tua_commit": RUNNER.tua_commit(args.tua_root), "code_sha256": RUNNER.code_sha256(),
                "base_config_sha256": RUNNER.sha256_file(RUNNER.BASE_CONFIG),
                "variant_config_sha256": RUNNER.sha256_file(RUNNER.CONFIGS["B"]),
                "task_list_sha256": RUNNER.sha256_file(RUNNER.CANONICAL_TASKS),
                "docker_default_platform": os.environ.get("DOCKER_DEFAULT_PLATFORM", ""), "cost_limit_usd": 0.06,
            }
            manifest_path.write_text(json.dumps(manifest))
            record = temp / "results" / "formal-B.csv"
            RUNNER.append_csv(record, {
                "suite": args.suite, "config_id": args.configuration, "task_id": task,
                "status": "completed", "cost_status": "complete", "agent_usd": "0.02",
                "trial_path": str(trial), "trajectory_path": str(trajectory),
                "manifest_path": str(manifest_path),
            })
            self.assertEqual(RUNNER.prior_action(args, task, record), "skip")
            args.model = "openrouter/other/model"
            with self.assertRaisesRegex(RuntimeError, "settings or code changed"):
                RUNNER.prior_action(args, task, record)

    def test_infrastructure_retry_requires_explicit_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            args = argparse.Namespace(run_root=temp / "runs", suite="formal", configuration="A",
                                      resume=True, retry_infrastructure=False)
            task = "000-count-nuclei"
            trial = args.run_root / args.suite / args.configuration / task / "trial-1"
            trial.mkdir(parents=True)
            record = temp / "results" / "formal-A.csv"
            RUNNER.append_csv(record, {
                "suite": args.suite, "config_id": args.configuration, "task_id": task,
                "status": "infrastructure_failure", "trial_path": str(trial),
            })
            with self.assertRaisesRegex(RuntimeError, "not a verified completed trial"):
                RUNNER.prior_action(args, task, record)
            args.retry_infrastructure = True
            self.assertEqual(RUNNER.prior_action(args, task, record), "retry")

    def test_formal_requires_all_forty_canonical_tasks(self):
        command = [
            sys.executable, "-B", str(SCRIPT), "--configuration", "B", "--suite", "formal",
            "--tua-root", str(ROOT), "--model", "openrouter/example/model", "--task", "000-count-nuclei",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("canonical 40-task list", completed.stderr)


if __name__ == "__main__":
    unittest.main()
