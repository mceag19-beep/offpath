"""Timeline states (the spine).

Exactly these states exist: NO_BASELINE, SAME_FAILURE, FAILURE_CHANGED,
RESOLVED, RETURNED_TO_PRIOR_STATE, UNKNOWN.

- NO_BASELINE: first relevant run with no previous comparable failure.
- SAME_FAILURE: same normalized signature as the relevant previous failure.
- FAILURE_CHANGED: the observed failure signature changed. This means new
  failure evidence was observed; it does NOT mean progress was made.
- RESOLVED: the command succeeds where a failure was previously tracked.
- RETURNED_TO_PRIOR_STATE: the recorded (diff identity, command identity,
  failure signature) tuple matches a previous attempt. The identity is
  intentionally limited and does not capture full environment state.
- UNKNOWN: execution visibility is insufficient for a reachability
  observation. UNKNOWN never disables failure-signature timeline tracking.

Coverage never drives the spine alone: state needs only command, diff
identity, and signature. Coverage amplifies with observed/not-observed
reachability detail when evidence quality allows.
"""

from __future__ import annotations

NO_BASELINE = "NO_BASELINE"
SAME_FAILURE = "SAME_FAILURE"
FAILURE_CHANGED = "FAILURE_CHANGED"
RESOLVED = "RESOLVED"
RETURNED_TO_PRIOR_STATE = "RETURNED_TO_PRIOR_STATE"
UNKNOWN = "UNKNOWN"

STATES = (
    NO_BASELINE,
    SAME_FAILURE,
    FAILURE_CHANGED,
    RESOLVED,
    RETURNED_TO_PRIOR_STATE,
    UNKNOWN,
)


def compute_state(
    exit_code: int,
    signature: str | None,
    diff_hash: str,
    cmd_str: str,
    events: list[dict],
    unknown: bool,
) -> tuple[str, dict]:
    """Return (state, extra) where extra holds matched_attempt/prev_signature.

    State strings are exactly the enum values above (no suffixes); details
    live in the extra fields so `status --json` stays machine-readable.
    """
    if unknown:
        return UNKNOWN, {}
    if exit_code == 0:
        return RESOLVED, {}
    for prev in reversed(events):
        if (
            prev.get("diff_hash") == diff_hash
            and prev.get("cmd") == cmd_str
            and prev.get("signature") == signature
            and signature is not None
        ):
            return RETURNED_TO_PRIOR_STATE, {"matched_attempt": prev["attempt"]}
    failing = [e for e in events if e.get("signature")]
    if not failing:
        return NO_BASELINE, {}
    prev_sig = failing[-1]["signature"]
    if prev_sig == signature:
        streak = 1
        for e in reversed(failing[:-1]):
            if e.get("signature") == signature:
                streak += 1
            else:
                break
        return SAME_FAILURE, {"streak": streak}
    return FAILURE_CHANGED, {"prev_signature": prev_sig}


def consecutive_no_signal(events: list[dict]) -> int:
    """Trailing streak of events carrying the NO_OBSERVED_SIGNAL verdict."""
    streak = 0
    for e in reversed(events):
        if "NO_OBSERVED_SIGNAL" in e.get("verdicts", []):
            streak += 1
        else:
            break
    return streak
