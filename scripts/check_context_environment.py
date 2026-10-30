#!/usr/bin/env python3
"""Read-only environment preflight for the user's VS Code terminal.

Only a local JSON report is written.  No benchmark, container, model request,
package installation, upload, or secret inspection is performed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TUA_COMMIT = "3497fd320abcafaf4797424192c891a593fd7964"
TASK_LIST = ROOT / "contributions/liu-yalin/developer_pack/settings/task_list_40.txt"


def command_output(arguments: list[str], *, cwd: Path | None = None) -> dict[str, str | int]:
    try:
        result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=15, check=False)
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout.strip()[:300],
            "stderr": result.stderr.strip()[:300],
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit_code": -1, "stdout": "", "stderr": type(error).__name__}


def check(tua_root: Path, *, skip_docker: bool) -> dict:
    uv_path = shutil.which("uv")
    docker_path = shutil.which("docker")
    git_path = shutil.which("git")
    task_ids = [line.strip() for line in TASK_LIST.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
    report = {
        "scheme_a_folder": str(ROOT),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "source_lock_exists": (ROOT / "source_lock.json").is_file(),
        "task_list_count": len(task_ids),
        "first_task_id": task_ids[0] if task_ids else "",
        "uv_path": uv_path or "missing",
        "uv_version": command_output([uv_path, "--version"]) if uv_path else {"exit_code": -1},
        "docker_path": docker_path or "missing",
        "docker_version": (
            "skipped" if skip_docker else command_output([docker_path, "version", "--format", "{{.Client.Version}}|{{.Server.Version}}"])
            if docker_path else {"exit_code": -1}
        ),
        "tua_root": str(tua_root),
        "tua_root_exists": tua_root.is_dir(),
        "tua_git_commit": command_output([git_path, "rev-parse", "HEAD"], cwd=tua_root) if git_path and tua_root.is_dir() else {"exit_code": -1},
        "expected_tua_commit": EXPECTED_TUA_COMMIT,
        "first_task_exists": (tua_root / "tasks" / task_ids[0]).exists() if tua_root.is_dir() and task_ids else False,
    }
    python_in_tua = tua_root / ".venv/bin/python"
    report["tua_venv_python_exists"] = python_in_tua.is_file()
    if python_in_tua.is_file():
        report["harbor_version"] = command_output([
            str(python_in_tua), "-B", "-c",
            "import importlib.metadata as m; print(m.version('harbor'))",
        ])
    else:
        report["harbor_version"] = {"exit_code": -1}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tua-root", type=Path, default=ROOT / "vendor/TUA-Bench")
    parser.add_argument("--output", type=Path, default=ROOT / "results/preflight/environment.json")
    parser.add_argument("--skip-docker", action="store_true", help="For script development only; user's preflight should check Docker")
    args = parser.parse_args()
    report = check(args.tua_root.expanduser().resolve(), skip_docker=args.skip_docker)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Preflight saved: {output}")


if __name__ == "__main__":
    main()
