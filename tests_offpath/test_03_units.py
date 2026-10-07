"""Unit tests: diff semantics, evidence grades, UNKNOWN matrix, states."""

from offpath import diffs, evidence, state, verdicts


def test_hunk_parsing_off_by_one_safe():
    # Inclusive-range intersection: git `+start,count` means
    # [start, start + count - 1]; executed lines use the same numbering.
    # (End-to-end hunk parsing is covered independently in test_02.)
    obs, not_obs, _ = diffs.intersect(
        {"a.py": [[10, 12]]}, {"a.py": [10, 12]}, set()
    )
    assert (obs, not_obs) == (2, 1)  # line 11 not executed
    obs, _, _ = diffs.intersect({"a.py": [[5, 5]]}, {"a.py": [5]}, set())
    assert obs == 1


def test_evidence_grades():
    assert evidence.evidence_grade(20, []) == "high"
    assert evidence.evidence_grade(847, []) == "high"
    assert evidence.evidence_grade(19, ["f.py:1:x"]) == "medium"
    assert evidence.evidence_grade(0, []) == "low"
    assert evidence.evidence_grade(0, ["f.py:1:x"]) == "medium"


def test_unknown_matrix():
    # Legitimate high-evidence zero-intersection run: never UNKNOWN.
    assert (
        evidence.visibility_unknown(1, "ValueError", 847, ["f.py:1:x"], 851)
        is False
    )
    # Passing run: RESOLVED path, never UNKNOWN even with no visibility.
    assert evidence.visibility_unknown(0, "ValueError", 0, [], 851) is False
    assert evidence.visibility_unknown(0, None, 0, [], None) is False
    # Real anomaly: nothing seen, baseline expected hundreds.
    assert evidence.visibility_unknown(1, "AssertionError", 0, [], 133) is True
    # No baseline yet: a real failure with ~nothing observed is anomalous.
    assert evidence.visibility_unknown(1, "ValueError", 0, [], None) is True
    # No failure at all and no baseline: not anomalous (nothing to explain).
    assert evidence.visibility_unknown(1, None, 5, [], None) is False
    # Measured frames alone defeat Condition A.
    assert evidence.visibility_unknown(1, "ValueError", 0, ["f.py:1:x"], 133) is False


def test_verdicts_neutral():
    assert verdicts.derive_verdicts(
        exit_code=1, unknown=False, changed={"a.py": [[1, 2]]},
        changed_observed=0, evidence="high",
    ) == ["NO_OBSERVED_SIGNAL"]
    # Suppressed when evidence is not high.
    assert verdicts.derive_verdicts(
        exit_code=1, unknown=False, changed={"a.py": [[1, 2]]},
        changed_observed=0, evidence="medium",
    ) == []
    # Suppressed on success and when something was observed.
    assert verdicts.derive_verdicts(
        exit_code=0, unknown=False, changed={"a.py": [[1, 2]]},
        changed_observed=0, evidence="high",
    ) == []
    assert verdicts.derive_verdicts(
        exit_code=1, unknown=False, changed={"a.py": [[1, 2]]},
        changed_observed=1, evidence="high",
    ) == []
    assert verdicts.derive_verdicts(
        exit_code=1, unknown=True, changed={}, changed_observed=0, evidence="low",
    ) == ["INSUFFICIENT_EXECUTION_EVIDENCE"]


def test_state_enums_exact():
    assert state.compute_state(0, None, "d", "c", [], False)[0] == "RESOLVED"
    assert state.compute_state(1, "s", "d", "c", [], True)[0] == "UNKNOWN"
    assert state.compute_state(1, "s", "d", "c", [], False)[0] == "NO_BASELINE"
    prev = [{"attempt": 1, "diff_hash": "d", "cmd": "c", "signature": "s"}]
    name, extra = state.compute_state(1, "s", "d", "c", prev, False)
    assert name == "RETURNED_TO_PRIOR_STATE"
    assert extra == {"matched_attempt": 1}
    # Same triple but different command: NOT a return (limited identity).
    name, _ = state.compute_state(1, "s", "d", "other", prev, False)
    assert name == "SAME_FAILURE"
    # Changed signature carries the previous signature for the message.
    name, extra = state.compute_state(1, "new", "d2", "c", prev, False)
    assert name == "FAILURE_CHANGED"
    assert extra == {"prev_signature": "s"}
