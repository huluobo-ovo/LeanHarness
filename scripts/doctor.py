"""Non-destructive local environment check for LeanLoop developers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def check(label: str, condition: bool, detail: str) -> bool:
    status = "OK" if condition else "MISSING"
    print(f"[{status:7}] {label}: {detail}")
    return condition


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ok = True
    ok &= check("Python", sys.version_info >= (3, 12), sys.version.split()[0])
    ok &= check("uv", shutil.which("uv") is not None, shutil.which("uv") or "not on PATH")

    bundled = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    docker = shutil.which("docker") or (str(bundled) if bundled.exists() else None)
    if docker:
        result = subprocess.run([docker, "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True)
        ok &= check("Docker", result.returncode == 0, result.stdout.strip() or result.stderr.strip())
    else:
        ok &= check("Docker CLI", False, "install/start Docker Desktop")

    ok &= check("TUA-Bench source", (root / "vendor" / "TUA-Bench" / "pyproject.toml").exists(), "vendor/TUA-Bench")
    ok &= check("mini-SWE-agent source", (root / "vendor" / "mini-swe-agent" / "pyproject.toml").exists(), "vendor/mini-swe-agent")
    key = os.environ.get("OPENROUTER_API_KEY")
    print("[INFO   ] OpenRouter key: " + ("set (not displayed)" if key else "not set; required only for real model runs"))
    print("[INFO   ] Workspace: " + str(root))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
