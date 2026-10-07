"""Run orchestration: one wrapped execution becomes one immutable attempt."""

from __future__ import annotations

import json
from pathlib import Path

from . import coverage_run, diffs, evidence, signature, state, store, verdicts
from .project import find_root
from .traceback_parse import parse_traceback


def do_run(cmd: list[str], root: Path | None = None) -> tuple[dict, int]:
    """Execute cmd, record one immutable event, return (event, exit_code)."""
    root = root or find_root()
    repo = diffs.require_git_repo(root)
    sdir = store.resolve_state_dir(repo)
    try:
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / store.RUNS_DIR).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise store.StoreError(f"cannot create state dir {sdir}: {exc}") from exc

    events = store.load_events(sdir)
    attempt = len(events) + 1
    cmd_str = " ".join(cmd)

    changed, diff_hash, raw_diff = diffs.changed_lines(repo)
    exit_code, output, executed, total, wall, collector = (
        coverage_run.run_under_coverage(cmd, repo, sdir)
    )

    exc_type, message, measured_frames, embedded_frames = parse_traceback(
        output, repo, executed
    )
    sig, sig_inputs = signature.make_signature(exc_type, message, measured_frames)
    if exit_code == 0:
        sig = None

    frame_files = {fr.rsplit(":", 2)[0] for fr in measured_frames}
    observed, not_observed, on_stack = diffs.intersect(changed, executed, frame_files)

    reference = evidence.reference_total(events)
    unknown = evidence.visibility_unknown(
        exit_code, exc_type, total, measured_frames, reference
    )
    grade = evidence.evidence_grade(total, measured_frames)
    state_name, extra = state.compute_state(
        exit_code, sig, diff_hash, cmd_str, events, unknown
    )
    verdict_list = verdicts.derive_verdicts(
        exit_code=exit_code,
        unknown=unknown,
        changed=changed,
        changed_observed=observed,
        evidence=grade,
    )

    env = store.env_fingerprint()
    event: dict = {
        "attempt": attempt,
        "cmd": cmd_str,
        "env_fingerprint": env,
        "diff_hash": diff_hash,
        "changed_lines": changed,
        "signature": sig,
        "signature_inputs": sig_inputs,
        "raw_traceback": output[-3000:],
        "normalized_message": message,
        "frame_chain": measured_frames,
        "embedded_frames": embedded_frames,
        "coverage": {
            "executed_lines": executed,
            "total_executed_lines": total,
            "baseline_executed_lines": reference,
            "collector": collector,
        },
        "intersection": {
            "changed_observed": observed,
            "changed_not_observed": not_observed,
            "changed_on_stack": on_stack,
        },
        "evidence": grade,
        "state": state_name,
        "verdicts": verdict_list,
        "wall_seconds": round(wall, 3),
        "exit_code": exit_code,
    }
    event.update(extra)
    if state_name == state.FAILURE_CHANGED:
        event["prev_signature"] = extra.get("prev_signature")

    rdir = store.run_dir(sdir, attempt)
    artifact_paths = store.write_artifacts(
        rdir,
        cmd_str=cmd_str,
        output=output,
        exit_code=exit_code,
        raw_diff=raw_diff,
        executed=executed,
        env=env,
        signature_inputs=sig_inputs,
        event_core={k: v for k, v in event.items()},
    )
    event["run_dir"] = str(rdir)
    event["artifacts"] = artifact_paths
    # Persist the traceable artifact map alongside the event.
    (rdir / "event.json").write_text(json.dumps(event, indent=1), encoding="utf-8")
    store.append_event(sdir, event)
    return event, exit_code


def gate_exit(event: dict, events_including_current: list[dict], gate: int | None) -> int | None:
    """Gate overrides: RETURNED_TO_PRIOR_STATE -> 3; N no-signal streak -> 2."""
    if event.get("state") == state.RETURNED_TO_PRIOR_STATE:
        return 3
    if gate is not None and state.consecutive_no_signal(events_including_current) >= gate:
        return 2
    return None


def ledger_line(current: dict, events: list[dict]) -> str | None:
    """Hypothesis ledger: attempts touching the same files (evidence only)."""
    files = list(current.get("changed_lines", {}).keys())
    if not files:
        return None
    touched = [
        e
        for e in events
        if set(e.get("changed_lines", {}).keys()) & set(files)
    ]
    sigs = {e.get("signature") for e in touched}
    sig_note = "no signature change" if len(sigs) <= 1 else f"{len(sigs)} distinct signatures"
    return (
        f"hypothesis ledger: {len(touched)} attempt(s) touching "
        f"{', '.join(sorted(set(files))[:3])}, {sig_note}"
    )


def format_human(event: dict, events: list[dict]) -> list[str]:
    n = event["attempt"]
    st = event["state"]
    lines: list[str] = []
    if st == state.UNKNOWN:
        lines.append(
            f"[offpath] attempt #{n} | UNKNOWN | insufficient execution evidence"
        )
        lines.append("[offpath] reachability observations withheld")
        lines.append("[offpath] failure signature timeline remains active")
        return lines
    if st == state.RETURNED_TO_PRIOR_STATE:
        matched = event.get("matched_attempt", "?")
        lines.append(f"[offpath] attempt #{n} | RETURNED_TO_PRIOR_STATE")
        lines.append(
            f"[offpath] matches recorded diff, command, and failure "
            f"signature of attempt #{matched}"
        )
        return lines
    sig = event.get("signature") or "-"
    lines.append(f"[offpath] attempt #{n} | {st} | signature {sig}")
    obs = event["intersection"]["changed_observed"]
    not_obs = event["intersection"]["changed_not_observed"]
    total_changed = obs + not_obs
    if total_changed:
        lines.append(
            f"[offpath] observed execution: {obs} of {total_changed} "
            f"changed lines recorded"
        )
    else:
        lines.append("[offpath] observed execution: no working-tree changes recorded")
    cov_total = event["coverage"]["total_executed_lines"]
    lines.append(f"[offpath] evidence: {event['evidence']} | {cov_total} executed lines")
    ledger = ledger_line(event, events)
    if ledger:
        lines.append(f"[offpath] {ledger}")
    if "NO_OBSERVED_SIGNAL" in event.get("verdicts", []):
        lines.append("[offpath] this hypothesis has produced no observed signal")
    return lines
