# OffPath Spike Report (template — fill with REAL outputs only)

Pass condition: all five scenarios produce the expected state with zero
false-positive reachability claims, and every verdict is independently
traceable from its JSONL event back to the stored run artifacts
(`.offpath/runs/NNN/`). Any failure: fix the evidence model and re-run
the full spike; record earlier failures in "Iteration log".

## Environment

- OS / arch:
- Python:
- pytest / coverage:
- CPU notes:

## Baseline

- Command: `python spike/offpath_spike.py baseline -- pytest tests/test_refund.py -x`
- Recorded baseline executed lines:

## Scenario results

For each: paste the `[offpath]` summary lines, the JSONL event (trimmed),
and the manual re-derivation check.

### S1 — off-path edit (pricing.py, flag off)

- Expected: `SAME_FAILURE`, evidence high, `NO_OBSERVED_SIGNAL`, observed 0/N
- Actual:
- Re-derivation (signature from signature_inputs, diff ranges vs executed):

### S2 — on-path edit (legacy_processor.py)

- Expected: `changed_observed > 0`
- Actual:

### S3 — failure moves deeper

- Expected: `FAILURE_CHANGED (old -> new)`, new signature KeyError at SETTLEMENT_ACCOUNTS
- Actual:

### S4 — return to prior state

- Expected: `RETURNED_TO_PRIOR_STATE (attempt #N)` referencing the S1b attempt
- Actual:

### S5 — subprocess + control

- Expected: subprocess `UNKNOWN` via visibility rules; control `RESOLVED`, not UNKNOWN
- Actual:
- Confirm UNKNOWN was triggered by BOTH conditions (no visibility source AND anomaly), not merely empty coverage:

## Verify output

```
(paste `python spike/offpath_spike.py verify`)
```

## Ledger

| Scenario | Expected state | Actual state | Evidence chain reproducible | Reachability claim sound | Pass |
|----------|----------------|--------------|------------------------------|---------------------------|------|
| S1 | | | | | |
| S2 | | | | | |
| S3 | | | | | |
| S4 | | | | | |
| S5 | | | | | |

Final: GREEN / RED

## Overhead

- Plain `pytest tests/test_refund.py -x`, 5 runs, median:
- Wrapped under OffPath, 5 runs, median:
- Multiplier:

## Iteration log

(Failures encountered during the spike, root cause, evidence-model fix applied.)

## Notes on provisional thresholds

The UNKNOWN heuristics (10% of baseline, <20 executed lines) are spike
scaffolding. Record here what the data suggests for a more robust
visibility-quality definition (decision deferred to post-spike).
