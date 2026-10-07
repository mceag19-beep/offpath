"""OffPath CLI: `run`, `status`. Exit codes documented below.

Exit codes for `offpath run`:
  0  command succeeded (wraps the command's own success)
  1  command failed (the command's own exit code propagates when no gate
     override applies; non-1 command failures propagate verbatim)
  2  gate tripped: N consecutive no-signal attempts
     (`offpath run --gate N -- <command>`; requires --gate)
  3  RETURNED_TO_PRIOR_STATE: the recorded (diff, command, signature) tuple
     matches a previous attempt (reported with or without --gate)

FAILURE_CHANGED is not success; RESOLVED is not just another failure.

NOTE: exit 2/3 take precedence over the wrapped command's own exit code.
A wrapped command that itself exits 2 or 3 is indistinguishable from a
gate signal; keep gate runs to test commands to avoid ambiguity.
"""

from __future__ import annotations

import json
import sys

from . import __version__, runner, store
from .diffs import GitError
from .project import find_root
from .store import StoreError

USAGE = """usage:
  offpath run [--gate N] -- <command...>
  offpath status [--json]
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    if argv[0] == "--version":
        sys.stdout.write(f"offpath {__version__}\n")
        return 0
    if argv[0] == "run":
        return cmd_run(argv[1:])
    if argv[0] == "status":
        return cmd_status(argv[1:])
    sys.stderr.write(f"unknown command: {argv[0]}\n{USAGE}")
    return 2


def cmd_run(args: list[str]) -> int:
    gate: int | None = None
    rest = list(args)
    if rest[:1] == ["--gate"]:
        if len(rest) < 3:
            sys.stderr.write("usage: offpath run --gate N -- <command...>\n")
            return 2
        try:
            gate = int(rest[1])
        except ValueError:
            sys.stderr.write("gate N must be an integer\n")
            return 2
        rest = rest[2:]
    if rest[:1] == ["--"]:
        rest = rest[1:]
    if not rest:
        sys.stderr.write("usage: offpath run [--gate N] -- <command...>\n")
        return 2
    try:
        event, exit_code = runner.do_run(rest)
    except (StoreError, GitError) as exc:
        sys.stderr.write(f"offpath: {exc}\n")
        return 2
    raw_output = ""
    try:
        with open(event["artifacts"]["output"], encoding="utf-8", errors="replace") as f:
            raw_output = f.read()
    except OSError:
        pass
    if raw_output:
        sys.stdout.write(raw_output if raw_output.endswith("\n") else raw_output + "\n")
    sys.stdout.write("\n".join(runner.format_human(event, _events_with(event))) + "\n")
    prior = _events_with(event)  # includes current
    override = runner.gate_exit(event, prior, gate)
    if override is not None:
        return override
    return exit_code


def _events_with(current: dict) -> list[dict]:
    root = find_root()
    sdir = store.resolve_state_dir(root)
    events = store.load_events(sdir)
    if not events or events[-1].get("attempt") != current.get("attempt"):
        events = events + [current]
    return events


def cmd_status(args: list[str]) -> int:
    as_json = "--json" in args
    root = find_root()
    sdir = store.resolve_state_dir(root)
    try:
        events = store.load_events(sdir)
    except (StoreError, GitError) as exc:
        sys.stderr.write(f"offpath: {exc}\n")
        return 2
    if as_json:
        payload = {
            "offpath": __version__,
            "count": len(events),
            "attempts": events,
            "last": events[-1] if events else None,
        }
        sys.stdout.write(json.dumps(payload, indent=1) + "\n")
        return 0
    if not events:
        sys.stdout.write("[offpath] no attempts recorded\n")
        return 0
    for e in events:
        sig = e.get("signature") or "-"
        sys.stdout.write(
            f"[offpath] #{e['attempt']} {e['state']} sig {sig} "
            f"evidence {e.get('evidence')} exit {e.get('exit_code')}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
