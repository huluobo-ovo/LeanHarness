from __future__ import annotations

from pathlib import Path

import pytest

from leanharness.integrations.harbor_role5_patch import PATCH_MARKER, apply_patch, render_patched_adapter, restore_patch


RUNTIME = Path("adapters/role5_runtime_agent.py")


def adapter_fixture() -> str:
    """A small syntax-valid stand-in containing Harbor 0.6.3's patch anchors."""
    return '''import json
import os
import shlex
from pathlib import Path

class BaseEnvironment: pass

class MiniSweAgent:
    def __init__(self, reasoning_effort=None, config_file=None, *args, **kwargs):
        self._reasoning_effort = reasoning_effort
        self._config_yaml: str | None = None
        if config_file:
            self._config_yaml = Path(config_file).read_text()

    @staticmethod
    def name() -> str:
        return "mini"

    async def exec_as_agent(self, environment, command, env=None):
        pass

    async def install(self, environment):
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
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


def test_rendered_adapter_contains_reversible_role5_integration():
    patched = render_patched_adapter(adapter_fixture(), RUNTIME.read_text())

    assert PATCH_MARKER in patched
    assert "role5_config_file" in patched
    assert "leanharness_role5.Role5DefaultAgent" in patched
    assert "_install_role5_runtime" in patched
    assert "effective_config_yaml" in patched


def test_patch_rejects_unknown_adapter_layout():
    with pytest.raises(ValueError, match="unsupported Harbor"):
        render_patched_adapter("import json\n", RUNTIME.read_text())


def test_apply_creates_backup_and_restore_recovers_exact_original(tmp_path):
    adapter = tmp_path / "mini_swe_agent.py"
    adapter.write_text(adapter_fixture())

    backup = apply_patch(adapter, RUNTIME)
    assert backup.exists()
    assert PATCH_MARKER in adapter.read_text()

    restore_patch(adapter)
    assert adapter.read_text() == adapter_fixture()
