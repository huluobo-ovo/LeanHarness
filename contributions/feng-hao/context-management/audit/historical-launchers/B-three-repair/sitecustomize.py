"""Opt-in public-dependency transport repair; no changes to agent logic or verifier."""
import os
import json
import re

def prepared_dockerfile(source):
    users = re.findall(r'^\s*USER\s+([^\n]+)', source, flags=re.M | re.I)
    if not users or users[-1].strip() != 'agent':
        raise RuntimeError('Unverified final Docker USER; refusing automatic preparation')
    # Apply before the original first apt instruction; keep original task source unchanged.
    stages = list(re.finditer(r'^\s*FROM[^\n]*\n', source, flags=re.M | re.I))
    first_from = stages[-1] if stages else None
    if not first_from:
        raise RuntimeError('Missing FROM')
    bootstrap = "COPY pe6203-ca.crt /etc/ssl/certs/ca-certificates.crt\nRUN find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) -exec sed -i -e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' -e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' -e 's|http://deb.debian.org|https://deb.debian.org|g' {} +\n"
    if 'openfoam/' in first_from.group(0).lower():
        bootstrap = 'USER root\n' + bootstrap
        source = source.replace('DEBIAN_FRONTEND=noninteractive apt-get update', '(DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 update || DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 update)')
    source = source[:first_from.end()] + bootstrap + source[first_from.end():]
    return source + '''\n# PE6203 infrastructure only: cache original build tools before agent setup.\nUSER root\nRUN if command -v gcc >/dev/null && command -v git >/dev/null && command -v curl >/dev/null; then :; else test -s /etc/ssl/certs/ca-certificates.crt && find /etc/apt -type f \\( -name '*.list' -o -name '*.sources' \\) -exec sed -i -e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' -e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' -e 's|http://deb.debian.org|https://deb.debian.org|g' {} + && apt-get update && (apt-get -o Acquire::Retries=3 install -y curl build-essential git || apt-get -o Acquire::Retries=3 install -y curl build-essential git); fi\nUSER agent\n'''

if os.environ.get('PE6203_REPAIR_A') == '1':
    from pathlib import Path
    from harbor.environments.docker.docker import DockerEnvironment
    from harbor.agents.installed.mini_swe_agent import MiniSweAgent
    overlay=Path(os.environ['PE6203_REPAIR_OVERLAY'])
    original_paths=DockerEnvironment._docker_compose_paths.fget
    def paths(self):
        folder = self.trial_paths.trial_dir
        folder.mkdir(parents=True, exist_ok=True)
        # Compose Bake permits Dockerfiles within the build context without
        # requesting additional filesystem entitlements.
        import shutil
        shutil.copyfile(Path(__file__).with_name('pe6203-ca.crt'), self.environment_dir / 'pe6203-ca.crt')
        text = prepared_dockerfile((self.environment_dir / 'Dockerfile').read_text())
        dockerfile = self.environment_dir / '.pe6203-agent-tools.Dockerfile'
        if not dockerfile.exists() or dockerfile.read_text() != text:
            dockerfile.write_text(text)
        (folder / 'Dockerfile.agent-tools').write_text(text)
        build_overlay = folder / 'compose-agent-tools.json'
        build_overlay.write_text(json.dumps({'services': {'main': {'build': {'dockerfile': dockerfile.name}}}}, indent=2))
        return [*original_paths(self), overlay, build_overlay]
    DockerEnvironment._docker_compose_paths=property(paths)
    async def install(self, environment):
        # Tools are built and cached before agent setup; never run apt inside setup.
        await self.exec_as_root(environment, command=(
            'command -v gcc && command -v git && command -v curl'),
            env={'DEBIAN_FRONTEND':'noninteractive'})
        await self.exec_as_agent(environment, command=(
            'set -euo pipefail; mkdir -p "$HOME/.local/bin"; '
            'cp /tmp/pe6203-uv-binary "$HOME/.local/bin/uv"; chmod +x "$HOME/.local/bin/uv"; '
            'printf \'%s\\n\' \'export PATH="$HOME/.local/bin:$PATH"\' > "$HOME/.local/bin/env"; '
            '. "$HOME/.local/bin/env"; uv --version; '
            'export UV_CACHE_DIR=/tmp/pe6203-uv-cache; '
            'uv tool install --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple '
            '--with "litellm[proxy]" mini-swe-agent==2.4.3; mini-swe-agent --help'))
        if self._context_config_path:
            await self._install_context_runtime(environment)
    MiniSweAgent.install=install
