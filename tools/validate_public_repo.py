# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "ok": completed.returncode == 0,
    }


def _check_markdown_links(repo_root: Path) -> dict:
    failures: list[str] = []
    checked = 0
    for path in repo_root.rglob("*.md"):
        if any(part in {"node_modules", ".runtime", "__pycache__"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            base_target = target.split("#", 1)[0]
            if not base_target:
                continue
            resolved = (path.parent / base_target).resolve()
            checked += 1
            if not resolved.exists():
                failures.append(f"{path.relative_to(repo_root)} -> {target}")
    return {
        "ok": not failures,
        "checked": checked,
        "failures": failures,
    }


def validate(repo_root: Path, *, python_executable: str) -> dict:
    temp_root = repo_root.parent / "_solaris_validate" / repo_root.name
    pytest_root = temp_root / "pt"
    pip_build_tracker = temp_root / "pbt"
    temp_root.mkdir(parents=True, exist_ok=True)
    pytest_root.mkdir(parents=True, exist_ok=True)
    pip_build_tracker.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMP"] = str(temp_root)
    env["TEMP"] = str(temp_root)
    env["PYTEST_DEBUG_TEMPROOT"] = str(pytest_root)
    env["PIP_BUILD_TRACKER"] = str(pip_build_tracker)

    commands = [
        [python_executable, "-m", "pip", "install", "--no-build-isolation", "-e", ".[dev]"],
        [python_executable, "-m", "pytest", f"--basetemp={pytest_root}"],
        [python_executable, ".\\run_retrieval_evals.py", "--json"],
        [python_executable, ".\\run_archive_state_model_checks.py", "--json"],
    ]
    command_results = [_run(command, cwd=repo_root, env=env) for command in commands]
    link_check = _check_markdown_links(repo_root)
    ok = all(result["ok"] for result in command_results) and link_check["ok"]
    return {
        "ok": ok,
        "repo_root": str(repo_root),
        "python": python_executable,
        "commands": command_results,
        "link_check": link_check,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the public Solaris validation stack against a standalone repo.")
    parser.add_argument(
        "--repo",
        type=Path,
        default=ROOT,
        help="Path to the standalone Solaris repository.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for validation commands.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output.",
    )
    args = parser.parse_args(argv)

    result = validate(args.repo.resolve(), python_executable=str(args.python))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Validation {'passed' if result['ok'] else 'failed'} for {result['repo_root']}")
        for item in result["commands"]:
            status = "PASS" if item["ok"] else "FAIL"
            print(f"{status} {' '.join(item['command'])}")
        if result["link_check"]["ok"]:
            print(f"PASS markdown links ({result['link_check']['checked']} checked)")
        else:
            print("FAIL markdown links")
            for failure in result["link_check"]["failures"]:
                print(f"  - {failure}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
