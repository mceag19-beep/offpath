"""Provisional visibility-quality thresholds (spike scaffolding, isolated here).

These numbers are NOT universally valid production truth. They are the
validated spike heuristics, kept isolated so they can be refined later
without touching the evidence model:

- HIGH_EVIDENCE_MIN_LINES: total executed project lines at or above this
  count qualify as high-quality execution evidence.
- UNKNOWN_MIN_LINES: below this executed-line count there is no meaningful
  coverage visibility source.
- UNKNOWN_BASELINE_FRACTION: an executed-line count below this fraction of
  the reference (prior high-evidence) total counts as anomalous.

UNKNOWN also requires a second, independent condition (an anomaly relative
to baseline expectations); see evidence.py. A legitimate high-evidence run
with zero changed-line intersection must NOT become UNKNOWN, and a passing
run becomes RESOLVED, never UNKNOWN.
"""

HIGH_EVIDENCE_MIN_LINES = 20
UNKNOWN_MIN_LINES = 20
UNKNOWN_BASELINE_FRACTION = 0.10
