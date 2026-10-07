"""S1-S5 timeline scenarios ported from the validated spike.

Order matters: the tests build one append-only timeline exactly like the
spike runbook (S1 -> S2 -> S3 -> S4 -> S5). Each test asserts the
implementation's derived fields; tests_offpath/test_evidence_independent.py
then re-derives the same claims from raw artifacts without trusting them.
"""

from tests_offpath.conftest import (
    CONTROL_CMD,
    LEGACY,
    LEGACY_S2,
    LEGACY_S3,
    PRICING,
    PRICING_S1,
    PRICING_S1B,
    PYTEST_CMD,
    SUBPROCESS_CMD,
    mutate,
)


def test_01_s1_offpath_edit_same_failure_no_signal(work):
    with mutate(PRICING, PRICING_S1):
        ev1, code1 = work.run(PYTEST_CMD)
    assert code1 != 0
    assert ev1["state"] == "NO_BASELINE"
    assert ev1["evidence"] == "high"

    with mutate(PRICING, PRICING_S1B):
        ev2, code2 = work.run(PYTEST_CMD)
    assert code2 != 0
    assert ev2["state"] == "SAME_FAILURE"
    assert ev2["signature"] == ev1["signature"]
    assert ev2["evidence"] == "high"
    assert ev2["verdicts"] == ["NO_OBSERVED_SIGNAL"]
    assert ev2["intersection"]["changed_observed"] == 0
    changed_total = (
        ev2["intersection"]["changed_observed"]
        + ev2["intersection"]["changed_not_observed"]
    )
    assert changed_total > 0
    # The off-path pricing ranges themselves are untouched by execution.
    pricing_ranges = ev2["changed_lines"].get("offpath_fixture/pricing.py", [])
    assert pricing_ranges, "S1 diff must touch pricing.py"
    executed = ev2["coverage"]["executed_lines"].get(
        "offpath_fixture/pricing.py", []
    )
    assert executed == []
    work.s1_sig = ev1["signature"]
    work.s1b_attempt = ev2["attempt"]


def test_02_s2_onpath_edit_observed(work):
    with mutate(LEGACY, LEGACY_S2):
        ev, code = work.run(PYTEST_CMD)
    assert code != 0
    assert ev["intersection"]["changed_observed"] > 0
    assert ev["verdicts"] == []
    # The edited on-path line is inside the changed ranges and executed.
    changed = ev["changed_lines"].get("offpath_fixture/legacy_processor.py", [])
    assert changed
    executed = set(
        ev["coverage"]["executed_lines"].get(
            "offpath_fixture/legacy_processor.py", []
        )
    )
    assert any(
        ln in executed for start, end in changed for ln in range(start, end + 1)
    )


def test_03_s3_failure_moves_deeper(work):
    with mutate(LEGACY, LEGACY_S3):
        ev, code = work.run(PYTEST_CMD)
    assert code != 0
    assert ev["state"] == "FAILURE_CHANGED"
    assert ev["signature"] != work.s1_sig
    assert ev["prev_signature"] == work.events[-2]["signature"]
    assert ev["signature_inputs"]["exception"] == "KeyError"
    work.s3_sig = ev["signature"]


def test_04_s4_returned_to_prior_state(work):
    with mutate(PRICING, PRICING_S1B):
        ev, code = work.run(PYTEST_CMD)
    assert code != 0
    assert ev["state"] == "RETURNED_TO_PRIOR_STATE"
    assert ev["matched_attempt"] == work.s1b_attempt
    # Limited identity tuple: diff + command + signature all match S1b.
    s1b = work.events[work.s1b_attempt - 1]
    assert ev["diff_hash"] == s1b["diff_hash"]
    assert ev["cmd"] == s1b["cmd"]
    assert ev["signature"] == s1b["signature"]


def test_05_s5_subprocess_unknown(work):
    ev, code = work.run(SUBPROCESS_CMD)
    assert code != 0
    assert ev["state"] == "UNKNOWN"
    assert ev["verdicts"] == ["INSUFFICIENT_EXECUTION_EVIDENCE"]
    assert ev["evidence"] == "low"
    # The measured/embedded distinction: child frames travel as text.
    assert ev["frame_chain"] == []
    assert len(ev["embedded_frames"]) > 0
    assert ev["coverage"]["total_executed_lines"] == 0
    # Both UNKNOWN conditions held: no visibility source AND anomaly.
    assert ev["coverage"]["baseline_executed_lines"] is not None
    assert ev["coverage"]["baseline_executed_lines"] > 0


def test_06_s5_control_resolved_not_unknown(work):
    ev, code = work.run(CONTROL_CMD)
    assert code == 0
    assert ev["state"] == "RESOLVED"
    assert ev["signature"] is None
    assert ev["evidence"] == "high"
