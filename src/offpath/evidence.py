"""Evidence quality + UNKNOWN visibility rules (validated spike logic).

Evidence quality is independent from state:
- high: genuine measured execution information (coverage footprint at or
  above the provisional threshold).
- medium: no coverage footprint, but measured project traceback frames.
- low: neither.

UNKNOWN requires BOTH:
  Condition A (no meaningful visibility source): executed-line count below
    the provisional minimum AND no measured project frames. Embedded
    traceback text never counts as measured execution.
  Condition B (anomaly): execution is anomalous relative to expectations --
    below the provisional fraction of the reference (prior high-evidence)
    total, or, with no reference available, a real failure ran but almost
    nothing was observed.

A legitimate high-evidence run with zero changed-line intersection is NOT
UNKNOWN. A passing run is RESOLVED, never UNKNOWN.
"""

from __future__ import annotations

from . import config

EVIDENCE_LEVELS = ("high", "medium", "low")


def evidence_grade(total_lines: int, measured_frames: list[str]) -> str:
    if total_lines >= config.HIGH_EVIDENCE_MIN_LINES:
        return "high"
    if measured_frames:
        return "medium"
    return "low"


def reference_total(events: list[dict]) -> int | None:
    """Reference footprint: max total over prior high-evidence runs."""
    totals = [
        e.get("coverage", {}).get("total_executed_lines", 0)
        for e in events
        if e.get("evidence") == "high"
    ]
    totals = [t for t in totals if isinstance(t, int) and t > 0]
    return max(totals) if totals else None


def visibility_unknown(
    exit_code: int,
    exc_type: str | None,
    executed_total: int,
    measured_frames: list[str],
    reference: int | None,
) -> bool:
    no_source = (
        executed_total < config.UNKNOWN_MIN_LINES and not measured_frames
    )
    if not no_source or exit_code == 0:
        return False
    if reference:
        anomaly = executed_total < config.UNKNOWN_BASELINE_FRACTION * reference
    else:
        anomaly = exc_type is not None
    return anomaly
