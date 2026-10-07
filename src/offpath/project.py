"""Repository root + project-file filter.

The spike hard-coded SOURCE_PREFIX="offpath_fixture". The MVP generalizes
this to "project files": Python files under the repository root, excluding
test harnesses, tooling, and environments. Test-harness lines are not
project execution evidence, and test-harness frames are not measured
execution (this is what keeps the S5 subprocess scenario UNKNOWN while a
passing control run is RESOLVED).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Test-harness config files that are never project evidence, at any level.
EXCLUDED_FILENAMES = {"conftest.py"}

# Directories (relative to repo root) that are never project evidence.
EXCLUDED_PREFIXES = (
    ".venv/",
    ".offpath/",
    ".git/",
    "tests/",
    "spike/",
    "src/offpath/",
    "tests_offpath/",
    "__pycache__/",
)


def find_root(start: Path | None = None) -> Path:
    """Return the repository top level (git), falling back to cwd."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start or Path.cwd()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except OSError:
        pass
    return Path(start or Path.cwd())


def state_dir(root: Path | None = None) -> Path:
    """Return the .offpath directory, honoring OFFPATH_DIR for tests."""
    override = os.environ.get("OFFPATH_DIR")
    if override:
        return Path(override)
    return (root or find_root()) / ".offpath"


def is_project_file(path_str: str, root: Path) -> bool:
    """True if path_str is repo-local project code (not tests/tooling/env)."""
    norm = path_str.replace("\\", "/")
    try:
        rel = Path(norm).resolve().relative_to(root.resolve())
    except ValueError:
        # Absolute path outside the repo (site-packages, stdlib, ...).
        # A bare relative path is resolved against the root.
        p = Path(norm)
        if p.is_absolute():
            return False
        rel = p
    rel_posix = rel.as_posix()
    if not rel_posix.endswith(".py"):
        return False
    if Path(rel_posix).name in EXCLUDED_FILENAMES:
        return False
    for prefix in EXCLUDED_PREFIXES:
        if rel_posix == prefix.rstrip("/") or rel_posix.startswith(prefix):
            return False
    return True


def to_rel_posix(path_str: str, root: Path) -> str:
    """Normalize an absolute/relative path to a root-relative posix path."""
    p = Path(path_str.replace("\\", "/"))
    if not p.is_absolute():
        p = root / p
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()
