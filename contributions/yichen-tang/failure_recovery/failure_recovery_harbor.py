"""Harbor agent for the failure recovery config.

Same as Harbor's built-in mini-swe-agent agent (so the litellm[proxy] patch still
applies), plus one step after install: copy fr_agent.py into the mini-swe-agent
tool environment in the container so `agent_class: fr_agent.FailureRecoveryAgent`
can be imported.
"""

from pathlib import Path

from harbor.agents.installed.mini_swe_agent import MiniSweAgent
from harbor.environments.base import BaseEnvironment

AGENT_FILE = Path(__file__).with_name("fr_agent.py")
TMP_PATH = "/tmp/fr_agent.py"


class FailureRecoveryMiniSweAgent(MiniSweAgent):
    async def install(self, environment: BaseEnvironment) -> None:
        await super().install(environment)
        await environment.upload_file(AGENT_FILE, TMP_PATH)
        await self.exec_as_root(environment, command=f"chmod a+r {TMP_PATH}")
        await self.exec_as_agent(
            environment,
            command=(
                'source "$HOME/.local/bin/env" && '
                'PY="$(uv tool dir)/mini-swe-agent/bin/python" && '
                'SP="$("$PY" -c "import sysconfig; print(sysconfig.get_paths()[\'purelib\'])")" && '
                f'cp {TMP_PATH} "$SP/fr_agent.py" && '
                '"$PY" -c "import fr_agent"'
            ),
        )
