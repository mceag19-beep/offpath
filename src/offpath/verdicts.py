"""Neutral evidence verdicts.

Verdict vocabulary (evidence only, never causality):
- NO_OBSERVED_SIGNAL: failing run, working-tree changes exist, evidence is
  high, but zero changed lines were observed executing. Reads as "this
  hypothesis has produced no observed signal", never "your edits cannot
  fix this".
- INSUFFICIENT_EXECUTION_EVIDENCE: visibility was insufficient (UNKNOWN);
  reachability observations are withheld while the failure-signature
  timeline remains active.
"""

from __future__ import annotations

NO_OBSERVED_SIGNAL = "NO_OBSERVED_SIGNAL"
INSUFFICIENT_EXECUTION_EVIDENCE = "INSUFFICIENT_EXECUTION_EVIDENCE"


def derive_verdicts(
    *,
    exit_code: int,
    unknown: bool,
    changed: dict,
    changed_observed: int,
    evidence: str,
) -> list[str]:
    if unknown:
        return [INSUFFICIENT_EXECUTION_EVIDENCE]
    if exit_code != 0 and changed and changed_observed == 0 and evidence == "high":
        return [NO_OBSERVED_SIGNAL]
    return []
