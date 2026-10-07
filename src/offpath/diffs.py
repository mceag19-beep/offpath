"""Working-tree diff tracking via `git diff -U0`.

Semantics (validated by the spike, off-by-one safe):
- Parse `git diff -U0 HEAD` (unstaged + staged vs HEAD).
- Each `@@ -a,b +start,count @@` hunk contributes the inclusive range
  [start, start + count - 1] on the NEW side of the diff.
- Pure deletions (count == 0) contribute nothing: there is no new-side
  line that coverage could observe.
- Untracked files are ignored (documented limitation).
- changed_lines maps "rel/posix/path.py" -> [[start, end], ...].
- diff_hash is a stable identity of the raw diff text (empty tree -> hash
  of the empty string), used as one leg of the RETURNED_TO_PRIOR_STATE
  identity tuple. It is intentionally limited: it does not capture
  environment or dependency state.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path


class GitError(Exception):
    """Git is missing, failing, or the directory is not a repository."""


def sha_short(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:8]


def _unquote_git_path(token: str) -> str:
    """Decode git's C-style quoted pathnames ("b/sp ace.py", octal UTF-8).

    Unquoted tokens pass through untouched. On undecodable input the raw
    inner text is returned: never crash on a strange filename.
    """
    if not (len(token) >= 2 and token.startswith('"') and token.endswith('"')):
        return token
    inner = token[1:-1]
    simple = {
        '"': b'"',
        "\\": b"\\",
        "t": b"\t",
        "n": b"\n",
        "r": b"\r",
        "b": b"\b",
        "f": b"\f",
        "v": b"\v",
        "a": b"\a",
    }
    out = bytearray()
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            octal = inner[i + 1 : i + 4]
            if len(octal) == 3 and all(c in "01234567" for c in octal):
                out.append(int(octal, 8))
                i += 4
                continue
            if nxt in simple:
                out += simple[nxt]
                i += 2
                continue
            out.append(ord(nxt))
            i += 2
            continue
        out += ch.encode("utf-8")
        i += 1
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        return inner


def _new_side_path(line: str) -> str | None:
    """Extract the new-side path from a `+++ ...` diff line.

    Returns None for deletions (`/dev/null`) and unrecognized shapes so
    subsequent hunks are never attributed to the wrong file. Missing a
    file suppresses verdicts (no claim); misattribution would fabricate
    them, so None is the conservative choice.
    """
    token = line[len("+++ ") :].split("\t")[0].strip()
    token = _unquote_git_path(token)
    if token == "/dev/null" or not token:
        return None
    if token.startswith("b/"):
        return token[len("b/") :] or None
    return None


def parse_diff_text(out: str) -> tuple[dict[str, list[list[int]]], str]:
    """Parse `git diff -U0` text into ({path: [[start, end]]}, diff_hash)."""
    result: dict[str, list[list[int]]] = {}
    current: str | None = None
    for line in out.splitlines():
        if line.startswith("+++ "):
            current = _new_side_path(line)
            if current is not None:
                result.setdefault(current, [])
        elif line.startswith("@@") and current:
            m = re.search(r"\+(\d+)(?:,(\d+))?\s*@@", line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2) or 1)
                if count > 0:
                    result[current].append([start, start + count - 1])
    # Drop files with no observable ranges (pure deletions).
    result = {k: v for k, v in result.items() if v}
    diff_hash = sha_short(out) if out.strip() else sha_short("")
    return result, diff_hash


def require_git_repo(root: Path) -> Path:
    """Return the repository top level, or raise GitError.

    OffPath tracks working-tree diffs, so a git repository is required.
    Refusing here is safer than recording a bogus "clean tree" attempt
    when git metadata is simply absent.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise GitError(f"git is not available: {exc}") from exc
    if proc.returncode != 0:
        raise GitError(
            f"not inside a git repository (checked {root}); "
            f"nothing was recorded."
        )
    return Path(proc.stdout.strip())


def changed_lines(root: Path) -> tuple[dict[str, list[list[int]]], str, str]:
    try:
        proc = subprocess.run(
            ["git", "diff", "-U0", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise GitError(f"git is not available: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {proc.returncode}"
        raise GitError(f"git diff failed: {tail}")
    changed, diff_hash = parse_diff_text(proc.stdout)
    return changed, diff_hash, proc.stdout


def intersect(
    changed: dict[str, list[list[int]]],
    executed: dict[str, list[int]],
    frame_files: set[str],
) -> tuple[int, int, int]:
    """Return (changed_observed, changed_not_observed, changed_on_stack).

    changed_on_stack counts changed lines in files appearing in the measured
    frame chain (file-level stack presence, not line-exact).
    """
    observed, not_observed, on_stack = 0, 0, 0
    for path, ranges in changed.items():
        executed_set = set(executed.get(path, []))
        on_stack_file = path in frame_files
        for start, end in ranges:
            for lineno in range(start, end + 1):
                if lineno in executed_set:
                    observed += 1
                else:
                    not_observed += 1
                if on_stack_file:
                    on_stack += 1
    return observed, not_observed, on_stack
