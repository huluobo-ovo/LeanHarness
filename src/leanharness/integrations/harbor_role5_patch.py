"""Render a reversible Harbor 0.6.3 adapter patch for Role 5."""

from __future__ import annotations

import base64
import shlex
from pathlib import Path


PATCH_MARKER = "# LeanHarness Role 5 integration (generated; do not edit by hand)"


def render_patched_adapter(adapter_text: str, runtime_source: str) -> str:
    """Add Role 5 support to Harbor 0.6.3's installed mini-SWE-agent adapter.

    The function uses narrow, version-specific anchors on purpose.  Refusing a
    changed adapter is safer than silently patching an unknown Harbor version.
    """
    if PATCH_MARKER in adapter_text:
        raise ValueError("adapter already contains the LeanHarness Role 5 integration")
    required = (
        "import json\n",
        "        self._reasoning_effort = reasoning_effort\n",
        "        await self.exec_as_agent(\n            environment,\n            command=(\n                \"set -euo pipefail; \"",
        "        # Write custom config into the container if provided\n",
    )
    missing = [anchor for anchor in required if anchor not in adapter_text]
    if missing:
        raise ValueError("unsupported Harbor mini_swe_agent.py layout; expected 0.6.3 anchors were not found")

    encoded_runtime = base64.b64encode(runtime_source.encode()).decode()
    imports = (
        "import base64\nimport json\nimport os\n"
        f"\n{PATCH_MARKER}\n_ROLE5_RUNTIME_B64 = {encoded_runtime!r}\n"
    )
    text = adapter_text.replace("import json\nimport os\n", imports, 1)
    install_command = 'f"uv tool install mini-swe-agent{version_spec} && "'
    if install_command not in text:
        raise ValueError("unsupported Harbor mini-SWE-agent install command")
    text = text.replace(
        install_command,
        'f"uv tool install --with \'litellm[proxy]\' mini-swe-agent{version_spec} && "',
        1,
    )
    text = text.replace(
        "        self._reasoning_effort = reasoning_effort\n        self._config_yaml: str | None = None\n",
        "        self._reasoning_effort = reasoning_effort\n"
        "        self._role5_config_path = kwargs.pop(\"role5_config_file\", None)\n"
        "        self._config_yaml: str | None = None\n",
        1,
    )
    insertion = '''\n    def _effective_config_yaml(self) -> str | None:\n        """Merge Role 5 tool settings into a private copy of the base config."""\n        if not self._role5_config_path:\n            return self._config_yaml\n        if not self._config_yaml:\n            raise ValueError("role5_config_file requires config_file")\n        import yaml\n\n        role5 = yaml.safe_load(Path(self._role5_config_path).read_text()) or {}\n        settings = ((role5.get("leanharness") or {}).get("tool_interface"))\n        if not isinstance(settings, dict):\n            raise ValueError("role5_config_file has no leanharness.tool_interface mapping")\n        base = yaml.safe_load(self._config_yaml) or {}\n        agent = base.setdefault("agent", {})\n        agent["agent_class"] = "leanharness_role5.Role5DefaultAgent"\n        agent["tool_interface"] = settings\n        return yaml.safe_dump(base, sort_keys=False)\n\n    async def _install_role5_runtime(self, environment: BaseEnvironment) -> None:\n        """Install the embedded overlay into mini-SWE-agent's uv tool venv."""\n        script = """import base64, pathlib, site, sys\\npathlib.Path(site.getsitepackages()[0], 'leanharness_role5.py').write_bytes(base64.b64decode(sys.argv[1]))\\n"""\n        command = (\n            '. "$HOME/.local/bin/env"; '\n            'mini_py="$(head -n 1 "$(command -v mini-swe-agent)" | sed "s/^#!//")"; '\n            '"$mini_py" -c ' + shlex.quote(script) + " " + shlex.quote(_ROLE5_RUNTIME_B64)\n        )\n        await self.exec_as_agent(environment, command=command)\n'''
    text = text.replace("    @staticmethod\n    def name() -> str:\n", insertion + "\n    @staticmethod\n    def name() -> str:\n", 1)
    install_tail = """                \"mini-swe-agent --help\"\n            ),\n        )\n"""
    replacement_tail = install_tail + "        if self._role5_config_path:\n            await self._install_role5_runtime(environment)\n"
    if install_tail not in text:
        raise ValueError("unsupported Harbor install block")
    text = text.replace(install_tail, replacement_tail, 1)
    text = text.replace(
        "        # Write custom config into the container if provided\n        config_flags = \"\"\n        if self._config_yaml:\n",
        "        # Write custom config into the container if provided\n        effective_config_yaml = self._effective_config_yaml()\n        config_flags = \"\"\n        if effective_config_yaml:\n",
        1,
    )
    text = text.replace("                f\"{self._config_yaml}\\n\"\n", "                f\"{effective_config_yaml}\\n\"\n", 1)
    return text


def apply_patch(adapter_path: Path, runtime_path: Path, *, backup_path: Path | None = None) -> Path:
    """Apply the version-locked patch, retaining an adjacent backup by default."""
    backup_path = backup_path or adapter_path.with_suffix(adapter_path.suffix + ".leanharness-role5.bak")
    if backup_path.exists():
        raise FileExistsError(f"backup already exists: {backup_path}; use --restore or remove it after inspection")
    original = adapter_path.read_text()
    patched = render_patched_adapter(original, runtime_path.read_text())
    backup_path.write_text(original)
    adapter_path.write_text(patched)
    return backup_path


def restore_patch(adapter_path: Path, backup_path: Path | None = None) -> None:
    """Restore the exact original adapter retained by :func:`apply_patch`."""
    backup_path = backup_path or adapter_path.with_suffix(adapter_path.suffix + ".leanharness-role5.bak")
    if not backup_path.exists():
        raise FileNotFoundError(f"backup not found: {backup_path}")
    adapter_path.write_text(backup_path.read_text())
