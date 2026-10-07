"""Gate mode, exit codes, and the JSON status contract (CLI-level tests).

Each test uses a FRESH isolated timeline (function tmp dir) so gate
semantics are verified independently of the S1-S5 session timeline.
"""

import json
import sys

from tests_offpath.conftest import (
    PRICING,
    PRICING_S1B,
    PRICING_S1C,
    PRICING_S1D,
    PYTEST_CMD,
    cli,
    mutate,
)

RUN = ["run", "--"]


def _run_gate(tmp_path, extra=()):
    return cli("run", *extra, "--", *PYTEST_CMD, offpath_dir=tmp_path)


def test_gate_no_signal_streak_exit_2(tmp_path):
    # Evolving diffs: consecutive no-signal attempts WITHOUT repeating a
    # recorded tuple (an exact rerun would report RETURNED_TO_PRIOR_STATE).
    with mutate(PRICING, PRICING_S1B):
        rc1, _ = _run_gate(tmp_path)
    with mutate(PRICING, PRICING_S1C):
        rc2, _ = _run_gate(tmp_path)
    assert (rc1, rc2) == (1, 1)
    with mutate(PRICING, PRICING_S1D):
        rc3, out3 = _run_gate(tmp_path, extra=("--gate", "2"))
    assert rc3 == 2
    assert "NO_OBSERVED_SIGNAL" not in out3  # human text stays neutral
    assert "no observed signal" in out3


def test_gate_below_threshold_preserves_command_exit(tmp_path):
    with mutate(PRICING, PRICING_S1B):
        rc, _ = _run_gate(tmp_path, extra=("--gate", "5"))
    assert rc == 1  # single no-signal attempt: command failure propagates


def test_gate_returned_to_prior_state_exit_3(tmp_path):
    with mutate(PRICING, PRICING_S1B):
        rc1, _ = _run_gate(tmp_path)
        assert rc1 == 1
        rc2, out2 = _run_gate(tmp_path, extra=("--gate", "2"))
    assert rc2 == 3  # returned-state takes precedence over the streak
    assert "RETURNED_TO_PRIOR_STATE" in out2
    assert "matches recorded diff, command, and failure signature" in out2


def test_returned_exit_3_without_gate(tmp_path):
    """RETURNED_TO_PRIOR_STATE exits 3 with or without --gate (documented)."""
    with mutate(PRICING, PRICING_S1B):
        assert _run_gate(tmp_path)[0] == 1
        rc, out = _run_gate(tmp_path)
    assert rc == 3
    assert "RETURNED_TO_PRIOR_STATE" in out


def test_status_json_contract(tmp_path):
    with mutate(PRICING, PRICING_S1B):
        _run_gate(tmp_path)
    rc, out = cli("status", "--json", offpath_dir=tmp_path)
    assert rc == 0
    payload = json.loads(out[out.index("{"):])
    assert set(payload) == {"offpath", "count", "attempts", "last"}
    assert payload["count"] == 1
    ev = payload["attempts"][0]
    for field in (
        "attempt", "cmd", "env_fingerprint", "diff_hash", "changed_lines",
        "signature", "signature_inputs", "coverage", "intersection",
        "evidence", "state", "verdicts",
    ):
        assert field in ev
    assert payload["last"]["attempt"] == 1
    assert ev["env_fingerprint"]["offpath"] is not None


def test_status_human_lists_attempts(tmp_path):
    with mutate(PRICING, PRICING_S1B):
        _run_gate(tmp_path)
        _run_gate(tmp_path)
    rc, out = cli("status", offpath_dir=tmp_path)
    assert rc == 0
    assert "#1" in out and "#2" in out


def test_run_propagates_command_failure_without_gate(tmp_path):
    with mutate(PRICING, PRICING_S1B):
        rc, out = cli("run", "--", *PYTEST_CMD, offpath_dir=tmp_path)
    assert rc == 1
    assert "SAME_FAILURE" in out or "NO_BASELINE" in out


def test_run_missing_command_usage(tmp_path):
    rc, out = cli("run", offpath_dir=tmp_path)
    assert rc == 2
    assert "usage" in out.lower()


def test_unknown_human_output_contract(tmp_path):
    rc, out = cli(
        "run", "--",
        sys.executable, "-m", "pytest", "tests/test_subprocess_refund.py", "-x",
        offpath_dir=tmp_path,
    )
    assert rc != 0
    assert "UNKNOWN" in out
    assert "insufficient execution evidence" in out
    assert "reachability observations withheld" in out
    assert "failure signature timeline remains active" in out
