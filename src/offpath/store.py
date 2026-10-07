"""Append-only timeline store + environment fingerprint + run artifacts."""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

from . import __version__
from .project import find_root, state_dir

EVENTS_FILE = "events.jsonl"
RUNS_DIR = "runs"


class StoreError(Exception):
    """The timeline or run artifacts cannot be read or written safely."""


def resolve_state_dir(root: Path | None = None) -> Path:
    root = root or find_root()
    return state_dir(root)


def load_events(sdir: Path) -> list[dict]:
    events_file = sdir / EVENTS_FILE
    if not events_file.exists():
        return []
    try:
        text = events_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise StoreError(f"cannot read timeline {events_file}: {exc}") from exc
    events = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise StoreError(
                    f"corrupt timeline {events_file} line {lineno}: {exc}. "
                    f"Delete or repair the file; no attempt was recorded."
                ) from exc
    return events


def append_event(sdir: Path, event: dict) -> None:
    try:
        sdir.mkdir(parents=True, exist_ok=True)
        with (sdir / EVENTS_FILE).open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError as exc:
        raise StoreError(f"cannot write timeline in {sdir}: {exc}") from exc


def run_dir(sdir: Path, attempt: int) -> Path:
    d = sdir / RUNS_DIR / f"{attempt:03d}"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StoreError(f"cannot create run directory {d}: {exc}") from exc
    return d


def env_fingerprint() -> dict:
    """Interpretive aid, NOT a complete reproducibility fingerprint."""
    relevant_env = {}
    for key, value in os.environ.items():
        if key.startswith("REFUND_") or key.startswith("OFFPATH_"):
            relevant_env[key] = value
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pytest": _pkg_version("pytest"),
        "coverage": _pkg_version("coverage"),
        "offpath": __version__,
        "relevant_env": relevant_env,
    }


def _pkg_version(name: str) -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version(name)
    except Exception:
        return "unknown"


def write_artifacts(
    rdir: Path,
    *,
    cmd_str: str,
    output: str,
    exit_code: int,
    raw_diff: str,
    executed: dict,
    env: dict,
    signature_inputs: dict,
    event_core: dict,
) -> dict:
    try:
        return _write_artifacts(
            rdir,
            cmd_str=cmd_str,
            output=output,
            exit_code=exit_code,
            raw_diff=raw_diff,
            executed=executed,
            env=env,
            signature_inputs=signature_inputs,
            event_core=event_core,
        )
    except OSError as exc:
        raise StoreError(f"cannot write run artifacts in {rdir}: {exc}") from exc


def _write_artifacts(
    rdir: Path,
    *,
    cmd_str: str,
    output: str,
    exit_code: int,
    raw_diff: str,
    executed: dict,
    env: dict,
    signature_inputs: dict,
    event_core: dict,
) -> dict:
    (rdir / "command.txt").write_text(cmd_str + "\n", encoding="utf-8")
    (rdir / "output.txt").write_text(output, encoding="utf-8")
    (rdir / "exit_code.txt").write_text(str(exit_code) + "\n", encoding="utf-8")
    (rdir / "diff.patch").write_text(raw_diff, encoding="utf-8")
    (rdir / "executed.json").write_text(json.dumps(executed, indent=1), encoding="utf-8")
    (rdir / "env.json").write_text(json.dumps(env, indent=1), encoding="utf-8")
    (rdir / "signature_inputs.json").write_text(
        json.dumps(signature_inputs, indent=1), encoding="utf-8"
    )
    (rdir / "event.json").write_text(json.dumps(event_core, indent=1), encoding="utf-8")
    return {
        "dir": str(rdir),
        "command": str(rdir / "command.txt"),
        "output": str(rdir / "output.txt"),
        "exit_code": str(rdir / "exit_code.txt"),
        "diff": str(rdir / "diff.patch"),
        "executed": str(rdir / "executed.json"),
        "env": str(rdir / "env.json"),
        "signature_inputs": str(rdir / "signature_inputs.json"),
        "event": str(rdir / "event.json"),
    }
