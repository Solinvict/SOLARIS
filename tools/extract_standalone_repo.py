# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT.parent / ".dist" / "solaris-standalone"

INCLUDE_PATHS = [
    ".env.example",
    ".github",
    ".gitignore",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "docs",
    "evals",
    "examples",
    "frontend",
    "migrations",
    "policies",
    "pyproject.toml",
    "rebuild_derived_artifacts.py",
    "rederive_entities.py",
    "run_adjudication_shadow_report.py",
    "run_archive_state_model_checks.py",
    "run_retrieval_evals.py",
    "run_server.py",
    "run_standalone.cmd",
    "run_standalone.ps1",
    "run_web.py",
    "src",
    "tests",
    "tools",
]

EXCLUDE_NAMES = {
    ".env",
    ".runtime",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
}

EXCLUDE_PREFIXES = (
    ".pytest-run",
    ".pytest-tmp",
    ".tmp",
    "pytest-cache-files-",
)

EXCLUDE_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".pyc",
    ".pyo",
    ".pyd",
)


def _should_skip(path: Path) -> bool:
    name = path.name
    if name in EXCLUDE_NAMES:
        return True
    if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return True
    if any(name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return True
    return False


def _ignore_factory():
    def _ignore(_directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            if _should_skip(Path(name)):
                ignored.add(name)
        return ignored

    return _ignore


def _copy_path(src_root: Path, dest_root: Path, relative_path: str) -> None:
    src = src_root / relative_path
    dest = dest_root / relative_path
    if not src.exists():
        raise FileNotFoundError(f"Missing include path: {relative_path}")
    if src.is_dir():
        shutil.copytree(src, dest, ignore=_ignore_factory(), dirs_exist_ok=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def extract(source_root: Path, destination_root: Path, *, force: bool) -> dict:
    if force and destination_root.exists():
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for relative_path in INCLUDE_PATHS:
        _copy_path(source_root, destination_root, relative_path)
        copied.append(relative_path)

    return {
        "source_root": str(source_root),
        "destination_root": str(destination_root),
        "copied": copied,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract Solaris into a clean standalone repository folder.")
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT,
        help="Path to the Solaris source root.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help="Destination folder for the standalone repository copy.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove the destination first if it already exists.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output.",
    )
    args = parser.parse_args(argv)

    result = extract(args.source.resolve(), args.dest.resolve(), force=args.force)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Extracted Solaris standalone repo to {result['destination_root']}")
        for path in result["copied"]:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
