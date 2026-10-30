"""Reversible, version-locked Harbor 0.6.3 integration for Scheme A."""

from __future__ import annotations

import base64
import shlex
from pathlib import Path


PATCH_MARKER = "# LeanHarness context integration (generated; do not edit by hand)"
ROLE5_MARKER = "# LeanHarness Role 5 integration"


def render_patched_adapter(adapter_text: str, runtime_source: str) -> str:
    """Add an optional context_config_file kwarg to Harbor's mini-SWE adapter.

    The shared LiteLLM proxy dependency fix is applied to all configurations.
    Without context_config_file, no context agent is installed or selected.
    """
    if PATCH_MARKER in adapter_text:
        raise ValueError("context integration already applied")
    if ROLE5_MARKER in adapter_text:
        raise ValueError("Role 5 adapter is active; restore it before applying the independent context adapter")
    required = (
        "import json\n",
        "        super().__init__(*args, **kwargs)\n        self._reasoning_effort = reasoning_effort\n",
        "        self._config_yaml: str | None = None\n",
        "        # Write custom config into the container if provided\n",
        "    @staticmethod\n    def name() -> str:\n",
    )
    missing = [anchor for anchor in required if anchor not in adapter_text]
    if missing:
        raise ValueError("unsupported Harbor mini_swe_agent.py layout; expected 0.6.3 anchors were not found")

    encoded = base64.b64encode(runtime_source.encode()).decode()
    imports = "import base64\nimport json\nimport os\n" + f"\n{PATCH_MARKER}\n_CONTEXT_RUNTIME_B64 = {encoded!r}\n"
    text = adapter_text.replace("import json\nimport os\n", imports, 1)

    original_install = 'f"uv tool install mini-swe-agent{version_spec} && "'
    fixed_install = 'f"uv tool install --with \'litellm[proxy]\' mini-swe-agent{version_spec} && "'
    if original_install in text:
        text = text.replace(original_install, fixed_install, 1)
    elif fixed_install not in text:
        raise ValueError("unsupported Harbor mini-SWE-agent install command")

    text = text.replace(
        "        super().__init__(*args, **kwargs)\n        self._reasoning_effort = reasoning_effort\n",
        "        self._context_config_path = kwargs.pop(\"context_config_file\", None)\n"
        "        super().__init__(*args, **kwargs)\n        self._reasoning_effort = reasoning_effort\n",
        1,
    )

    insertion = '''\n    def _effective_config_yaml(self) -> str | None:\n        if not self._context_config_path:\n            return self._config_yaml\n        if not self._config_yaml:\n            raise ValueError("context_config_file requires config_file")\n        import yaml\n\n        context = yaml.safe_load(Path(self._context_config_path).read_text()) or {}\n        settings = ((context.get("leanharness") or {}).get("context_management"))\n        if not isinstance(settings, dict):\n            raise ValueError("context_config_file has no leanharness.context_management mapping")\n        base = yaml.safe_load(self._config_yaml) or {}\n        agent = base.setdefault("agent", {})\n        agent["agent_class"] = "leanharness_context.ContextDefaultAgent"\n        agent["context_management"] = settings\n        return yaml.safe_dump(base, sort_keys=False)\n\n    async def _install_context_runtime(self, environment: BaseEnvironment) -> None:\n        """Install the embedded overlay into mini-SWE-agent's uv tool venv."""\n        script = """import base64, pathlib, site, sys\\npathlib.Path(site.getsitepackages()[0], 'leanharness_context.py').write_bytes(base64.b64decode(sys.argv[1]))\\n"""\n        command = (\n            '. "$HOME/.local/bin/env"; '\n            'mini_py="$(head -n 1 "$(command -v mini-swe-agent)" | sed "s/^#!//")"; '\n            '"$mini_py" -c ' + shlex.quote(script) + " " + shlex.quote(_CONTEXT_RUNTIME_B64)\n        )\n        await self.exec_as_agent(environment, command=command)\n'''
    text = text.replace("    @staticmethod\n    def name() -> str:\n", insertion + "\n    @staticmethod\n    def name() -> str:\n", 1)

    install_tail = '                "mini-swe-agent --help"\n            ),\n        )\n'
    if install_tail not in text:
        raise ValueError("unsupported Harbor install block")
    text = text.replace(
        install_tail,
        install_tail + "        if self._context_config_path:\n            await self._install_context_runtime(environment)\n",
        1,
    )

    run_anchor = (
        "        # Write custom config into the container if provided\n"
        "        config_flags = \"\"\n"
        "        if self._config_yaml:\n"
    )
    if run_anchor not in text:
        raise ValueError("unsupported Harbor config-writing block")
    text = text.replace(
        run_anchor,
        "        # Write custom config into the container if provided\n"
        "        effective_config_yaml = self._effective_config_yaml()\n"
        "        config_flags = \"\"\n"
        "        if effective_config_yaml:\n",
        1,
    )
    old_yaml_line = '                f"{self._config_yaml}\\n"\n'
    if old_yaml_line not in text:
        raise ValueError("unsupported Harbor config heredoc")
    text = text.replace(old_yaml_line, '                f"{effective_config_yaml}\\n"\n', 1)
    return text


def apply_patch(adapter_path: Path, runtime_path: Path, *, backup_path: Path | None = None) -> Path:
    backup_path = backup_path or adapter_path.with_suffix(adapter_path.suffix + ".leanharness-context.bak")
    if backup_path.exists():
        raise FileExistsError(f"backup already exists: {backup_path}")
    original = adapter_path.read_text()
    patched = render_patched_adapter(original, runtime_path.read_text())
    backup_path.write_text(original)
    adapter_path.write_text(patched)
    return backup_path


def restore_patch(adapter_path: Path, backup_path: Path | None = None) -> None:
    backup_path = backup_path or adapter_path.with_suffix(adapter_path.suffix + ".leanharness-context.bak")
    if not backup_path.exists():
        raise FileNotFoundError(f"backup not found: {backup_path}")
    if PATCH_MARKER not in adapter_path.read_text():
        raise ValueError("adapter no longer contains this context patch; refusing to overwrite subsequent changes")
    adapter_path.write_text(backup_path.read_text())
    backup_path.unlink()
