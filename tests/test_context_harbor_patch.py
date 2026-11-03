"""Offline tests for the reversible Harbor 0.6.3 integration."""

from __future__ import annotations

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src/leanharness/integrations/harbor_context_patch.py"
SPEC = importlib.util.spec_from_file_location("harbor_context_patch_test", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


# The anchors and order match Harbor v0.6.3's official mini_swe_agent.py.
HARBOR_FRAGMENT = '''import json
import os
import shlex
from pathlib import Path
class MiniSweAgent:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._reasoning_effort = reasoning_effort
        self._config_yaml: str | None = None
    @staticmethod
    def name() -> str:
        return "mini-swe-agent"
    async def install(self, environment):
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                f"uv tool install mini-swe-agent{version_spec} && "
                "mini-swe-agent --help"
            ),
        )
    async def run(self, environment):
        # Write custom config into the container if provided
        config_flags = ""
        if self._config_yaml:
            write_config_cmd = (
                f"{self._config_yaml}\\n"
            )
'''


class ContextHarborPatchTests(unittest.TestCase):
    def test_generates_valid_optional_adapter(self):
        runtime = (ROOT / "adapters/context_runtime_agent.py").read_text()
        generated = PATCH.render_patched_adapter(HARBOR_FRAGMENT, runtime)
        ast.parse(generated)
        self.assertIn("kwargs.pop(\"context_config_file\", None)", generated)
        self.assertIn("if self._context_config_path:", generated)
        self.assertIn("leanharness_context.ContextDefaultAgent", generated)
        self.assertIn("uv tool install --with 'litellm[proxy]'", generated)
        self.assertNotIn("role5_config_file", generated)
        self.assertIn("return self._config_yaml", generated)

    def test_refuses_unknown_or_competing_adapter(self):
        runtime = (ROOT / "adapters/context_runtime_agent.py").read_text()
        with self.assertRaisesRegex(ValueError, "unsupported"):
            PATCH.render_patched_adapter("class Unknown: pass", runtime)
        with self.assertRaisesRegex(ValueError, "Role 5"):
            PATCH.render_patched_adapter(PATCH.ROLE5_MARKER + "\n" + HARBOR_FRAGMENT, runtime)
        generated = PATCH.render_patched_adapter(HARBOR_FRAGMENT, runtime)
        with self.assertRaisesRegex(ValueError, "already applied"):
            PATCH.render_patched_adapter(generated, runtime)

    def test_apply_restore_reapply_preserves_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory) / "mini_swe_agent.py"
            adapter.write_text(HARBOR_FRAGMENT)
            runtime = ROOT / "adapters/context_runtime_agent.py"
            backup = PATCH.apply_patch(adapter, runtime)
            self.assertEqual(backup.read_text(), HARBOR_FRAGMENT)
            self.assertNotEqual(adapter.read_text(), HARBOR_FRAGMENT)
            PATCH.restore_patch(adapter, backup)
            self.assertEqual(adapter.read_text(), HARBOR_FRAGMENT)
            self.assertFalse(backup.exists(), "restore should permit the next deliberate apply")
            PATCH.apply_patch(adapter, runtime)


if __name__ == "__main__":
    unittest.main()
