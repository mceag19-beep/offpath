"""Coverage collection (coverage.py amplifier).

Runs the wrapped command out-of-process under `coverage run` and extracts
executed lines for project files only (see project.py). If coverage is
unavailable or unusable, the spine still works: the run is recorded with
empty execution data and low evidence instead of failing.

Runner boundary: pytest is the supported MVP runner. Arbitrary commands
pass through `coverage run <cmd>`; non-Python commands yield empty
execution data (documented limitation).

Child output is decoded as UTF-8 (errors replaced, never crashing, never
locale-dependent mojibake): signatures stay deterministic for identical
child bytes on any machine.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from .project import is_project_file, to_rel_posix


def run_under_coverage(
    cmd: list[str], root: Path, state_dir: Path
) -> tuple[int, str, dict[str, list[int]], int, float, str]:
    """Return (exit_code, output, executed, total, wall_seconds, collector).

    collector is "coverage.py", or "coverage.py (unavailable: <reason>)" /
    "coverage.py (unusable: <reason>)" when falling back to a plain run.
    """
    data_file = state_dir / ".coverage.tmp"
    try:
        import coverage  # noqa: F401
    except ImportError:
        return _plain_run(cmd, root, "coverage.py (unavailable: not installed)")

    if cmd[0] == "pytest":
        cov_cmd = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--data-file",
            str(data_file),
            "-m",
            "pytest",
            *cmd[1:],
        ]
    elif (
        len(cmd) >= 3
        and cmd[1] == "-m"
        and cmd[2].split(".")[0] == "pytest"
        and Path(cmd[0]).name.lower().startswith("python")
    ):
        # `python -m pytest ...` spelling of the pytest runner.
        cov_cmd = [
            cmd[0],
            "-m",
            "coverage",
            "run",
            "--data-file",
            str(data_file),
            "-m",
            "pytest",
            *cmd[3:],
        ]
    elif Path(cmd[0]).suffix.lower() == ".py":
        cov_cmd = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--data-file",
            str(data_file),
            *cmd,
        ]
    else:
        # Arbitrary binaries cannot be wrapped by coverage.py: record the
        # run on the spine (no execution amplifier) instead of failing.
        return _plain_run(
            cmd, root, "coverage.py (unavailable: non-Python command)"
        )
    start = time.time()
    proc = subprocess.run(
        cov_cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    wall = time.time() - start
    output = proc.stdout + proc.stderr
    try:
        import coverage

        cov = coverage.Coverage(data_file=str(data_file))
        cov.load()
        executed: dict[str, list[int]] = {}
        total = 0
        for measured in cov.get_data().measured_files():
            if not is_project_file(measured, root):
                continue
            lines = sorted(
                ln for ln in (cov.get_data().lines(measured) or []) if ln > 0
            )
            rel = to_rel_posix(measured, root)
            executed[rel] = lines
            total += len(lines)
    except Exception as exc:  # corrupt/empty data file: spine survives
        try:
            data_file.unlink(missing_ok=True)
        except OSError:
            pass
        return proc.returncode, output, {}, 0, wall, (
            f"coverage.py (unusable: {exc})"
        )
    try:
        data_file.unlink(missing_ok=True)
    except OSError:
        pass
    return proc.returncode, output, executed, total, wall, "coverage.py"


def _plain_run(
    cmd: list[str], root: Path, collector: str
) -> tuple[int, str, dict[str, list[int]], int, float, str]:
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        return 127, f"command not found: {exc}\n", {}, 0, 0.0, collector
    wall = time.time() - start
    return proc.returncode, proc.stdout + proc.stderr, {}, 0, wall, collector
