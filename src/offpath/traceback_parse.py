"""Traceback parsing with measured vs embedded frames.

measured_frames: frames from the process's own traceback, i.e. lines where
  the `File "...", line N` token starts the line (leading whitespace only)
  AND the file shows measured execution in this run's coverage. A frame
  for a file with zero executed lines is not execution evidence — it is
  indistinguishable from transported text (e.g. a child process's stderr
  rendered without a prefix) — so it is demoted to embedded. This
  cross-check is one-directional and conservative: it can only withhold a
  reachability observation, never fabricate one.

embedded_frames: project frames merely quoted inside captured text, e.g. a
  child process's stderr transported inside a parent AssertionError message
  (the S5 subprocess shape), plus any line-start frames demoted for lack
  of coverage support. These are text, NOT execution evidence, and must
  never count as visibility.

Frames outside project code (test harness, site-packages, stdlib) are
ignored entirely: they are neither measured nor embedded.
"""

from __future__ import annotations

import re
from pathlib import Path

from .project import is_project_file, to_rel_posix

_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+)(?:, in ([\w<>]+))?')


def parse_traceback(
    output: str, root: Path, executed: dict[str, list[int]] | None = None
) -> tuple[str | None, str | None, list[str], list[str]]:
    exc_type: str | None = None
    message: str | None = None

    m = re.search(r"^E\s+(\w+(?:\.\w+)*):\s*(.*)$", output, re.M)
    if m:
        exc_type, message = m.group(1), m.group(2)
    if exc_type is None:
        m = re.search(
            r"^(\w+(?:Error|Exception|Exit|Interrupt|Warning)):\s*(.*)$",
            output,
            re.M,
        )
        if m:
            exc_type, message = m.group(1), m.group(2)
    if exc_type is None:
        m = re.search(r"(AssertionError):\s*(assert[^\n]*)", output)
        if m:
            exc_type, message = m.group(1), m.group(2)

    measured: list[str] = []
    embedded: list[str] = []
    for fm in _FRAME_RE.finditer(output):
        path, lineno, func = fm.group(1), int(fm.group(2)), fm.group(3) or "?"
        if not is_project_file(path, root):
            continue
        rel = to_rel_posix(path, root)
        entry = f"{rel}:{lineno}:{func}"
        line_start = output.rfind("\n", 0, fm.start()) + 1
        if output[line_start : fm.start()].strip() == "":
            measured.append(entry)
        else:
            embedded.append(entry)

    if executed is not None:
        measured, embedded = validate_measured_frames(measured, embedded, executed)

    if message is not None:
        message = _normalize_message(message)
    return exc_type, message, measured, embedded


def validate_measured_frames(
    measured: list[str],
    embedded: list[str],
    executed: dict[str, list[int]],
) -> tuple[list[str], list[str]]:
    """Demote line-start frames whose file shows no measured execution.

    File-level (not line-exact): a frame is kept as measured when its file
    has at least one executed line in this run's coverage. Line-exact
    matching would be brittle against traceback/coverage line attribution
    differences (multi-line statements, decorators). Demoted frames move
    to embedded (without duplicating entries already there).
    """
    kept, demoted = [], list(embedded)
    for entry in measured:
        rel = entry.rsplit(":", 2)[0]
        if executed.get(rel):
            kept.append(entry)
        elif entry not in demoted:
            demoted.append(entry)
    return kept, demoted


def _normalize_message(message: str) -> str:
    message = re.sub(r"0x[0-9a-fA-F]+", "<hex>", message)
    message = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<uuid>",
        message,
    )
    message = re.sub(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?", "<ts>", message
    )
    message = message.replace("\\n", " ").strip()
    return message
