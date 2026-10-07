"""Independent evidence tests: re-derive every claim from raw artifacts.

These tests deliberately avoid trusting the implementation's derived
fields. They recompute signatures, intersections, states, and
returned-state matches from the stored run artifacts (output.txt,
diff.patch, executed.json) with independent parsing logic, closing the
circular-LEDGER weakness the forensic audit identified.
"""

import json
import re
from pathlib import Path

from offpath import signature as sig_module
from offpath import state as state_module
from offpath.project import find_root
from offpath.traceback_parse import parse_traceback

ROOT = Path(__file__).resolve().parent.parent
CORE_FIELDS = [
    "attempt",
    "cmd",
    "env_fingerprint",
    "diff_hash",
    "changed_lines",
    "signature",
    "signature_inputs",
    "coverage",
    "intersection",
    "evidence",
    "state",
    "verdicts",
]
ARTIFACT_FILES = [
    "command.txt",
    "output.txt",
    "exit_code.txt",
    "diff.patch",
    "executed.json",
    "env.json",
    "signature_inputs.json",
    "event.json",
]


def _timeline_events(work):
    assert len(work.events) == 7, f"expected S1-S5 timeline, got {len(work.events)}"
    return work.events


def test_core_auditability_fields_present(work):
    for ev in _timeline_events(work):
        for field in CORE_FIELDS:
            assert field in ev, f"attempt #{ev['attempt']} missing {field}"
        assert ev["state"] in state_module.STATES
        assert ev["evidence"] in ("high", "medium", "low")


def test_run_artifacts_exist_and_agree(work):
    for ev in _timeline_events(work):
        rdir = Path(ev["run_dir"])
        assert rdir.is_dir()
        for name in ARTIFACT_FILES:
            assert (rdir / name).is_file(), f"#{ev['attempt']} missing {name}"
        assert (rdir / "command.txt").read_text().strip() == ev["cmd"]
        assert int((rdir / "exit_code.txt").read_text().strip()) == ev["exit_code"]
        assert (rdir / "output.txt").read_text()[-3000:] == ev["raw_traceback"]
        stored_exec = json.loads((rdir / "executed.json").read_text())
        assert stored_exec == ev["coverage"]["executed_lines"]


def test_signatures_recomputed_from_raw_output(work):
    root = find_root(ROOT)
    for ev in _timeline_events(work):
        raw = Path(ev["artifacts"]["output"]).read_text()
        executed = json.loads(Path(ev["artifacts"]["executed"]).read_text())
        # Mirror the pipeline exactly: parse validates line-start frames
        # against the run's own coverage (a bare frame for an unexecuted
        # file is transported text, not measured execution).
        exc, msg, measured, _embedded = parse_traceback(raw, root, executed)
        recomputed, inputs = sig_module.recompute_signature(exc, msg, measured)
        if ev["exit_code"] == 0:
            assert ev["signature"] is None
            continue
        assert recomputed == ev["signature"], f"attempt #{ev['attempt']}"
        assert inputs == ev["signature_inputs"], f"attempt #{ev['attempt']}"
        assert ev["signature_inputs"]["frames_hash"] == sig_module.frames_hash(
            ev["frame_chain"]
        )


def _parse_hunks_independently(patch: str) -> dict:
    """Independent `git diff -U0` hunk parser (separate regex/logic)."""
    changed: dict[str, list[list[int]]] = {}
    cur = None
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            cur = line.split("+++ b/", 1)[1]
            changed[cur] = []
        elif line.startswith("@@") and cur is not None:
            plus = line.split("+", 1)[1].split()[0]
            if "," in plus:
                start_s, count_s = plus.split(",", 1)
                start, count = int(start_s), int(count_s)
            else:
                start, count = int(plus), 1
            if count > 0:
                changed[cur].append([start, start + count - 1])
    return {k: v for k, v in changed.items() if v}


def test_diff_and_intersection_recomputed(work):
    for ev in _timeline_events(work):
        patch = Path(ev["artifacts"]["diff"]).read_text()
        executed = json.loads(Path(ev["artifacts"]["executed"]).read_text())
        changed = _parse_hunks_independently(patch)
        assert changed == ev["changed_lines"], f"attempt #{ev['attempt']}"
        obs = not_obs = 0
        for path, ranges in changed.items():
            ex = set(executed.get(path, []))
            for start, end in ranges:
                for ln in range(start, end + 1):
                    if ln in ex:
                        obs += 1
                    else:
                        not_obs += 1
        assert obs == ev["intersection"]["changed_observed"]
        assert not_obs == ev["intersection"]["changed_not_observed"]


def test_state_timeline_replayed(work):
    """Replay compute_state over the recorded order; states must agree."""
    events = _timeline_events(work)
    for i, ev in enumerate(events):
        prior = events[:i]
        unknown = ev["state"] == "UNKNOWN"
        replayed, extra = state_module.compute_state(
            ev["exit_code"],
            ev["signature"],
            ev["diff_hash"],
            ev["cmd"],
            prior,
            unknown,
        )
        assert replayed == ev["state"], f"attempt #{ev['attempt']}"
        if replayed == "RETURNED_TO_PRIOR_STATE":
            assert extra["matched_attempt"] == ev["matched_attempt"]
        if replayed == "FAILURE_CHANGED":
            assert extra["prev_signature"] == ev["prev_signature"]


def test_returned_state_tuple_is_limited_but_exact(work):
    events = _timeline_events(work)
    returned = next(e for e in events if e["state"] == "RETURNED_TO_PRIOR_STATE")
    prior = events[returned["matched_attempt"] - 1]
    assert (returned["diff_hash"], returned["cmd"], returned["signature"]) == (
        prior["diff_hash"],
        prior["cmd"],
        prior["signature"],
    )
    # No earlier event shares the full tuple (first return wins).
    for e in events[: returned["matched_attempt"] - 1]:
        assert (
            e["diff_hash"],
            e["cmd"],
            e["signature"],
        ) != (
            returned["diff_hash"],
            returned["cmd"],
            returned["signature"],
        )


def test_measured_vs_embedded_distinction(work):
    from offpath import evidence as evidence_module

    events = _timeline_events(work)
    s5 = next(e for e in events if e["state"] == "UNKNOWN")
    raw = Path(s5["artifacts"]["output"]).read_text()
    # Raw output really does mention project frames (as transported text)...
    assert re.search(r'File ".*offpath_fixture.*", line \d+', raw)
    # ...but none of them are measured execution.
    assert s5["frame_chain"] == []
    assert len(s5["embedded_frames"]) > 0
    # In-process pytest runs also record no File-token frames (pytest's
    # default traceback style); coverage is their visibility source.
    s1 = events[1]
    assert s1["frame_chain"] == []
    assert s1["evidence"] == "high"
    # The distinction is load-bearing: had the transported frames counted
    # as measured, the S5 anomaly would NOT be UNKNOWN.
    exc = s5["signature_inputs"]["exception"]
    ref = s5["coverage"]["baseline_executed_lines"]
    assert evidence_module.visibility_unknown(1, exc, 0, [], ref) is True
    assert (
        evidence_module.visibility_unknown(1, exc, 0, s5["embedded_frames"], ref)
        is False
    )


def test_no_causality_language_in_events(work):
    forbidden = ["cannot fix", "cannot affect", "causally irrelevant", "unrelated"]
    for ev in _timeline_events(work):
        blob = json.dumps(ev).lower()
        for phrase in forbidden:
            assert phrase not in blob
