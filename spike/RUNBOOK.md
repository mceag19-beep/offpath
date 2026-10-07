# OffPath Spike Runbook

Execute from the repo root on branch `spike/evidence-model`, in this exact order.
Record real numbers in `spike/REPORT.md` as you go. Do not skip steps or
reorder; the ledger depends on the timeline.

## 0. Setup

```bash
git checkout spike/evidence-model
python3 -m venv .venv && source .venv/bin/activate
pip install -r spike/requirements.txt
```

Sanity check (plain, unwrapped): `pytest tests/test_refund.py -x` must FAIL
with `ValueError: invalid currency` at `legacy_processor.py`.

## 1. Baseline

```bash
rm -rf .offpath                       # fresh timeline
python spike/offpath_spike.py baseline -- pytest tests/test_refund.py -x
```

Note the recorded baseline executed-line count in the report.

## 2. S1: off-path edit (pricing.py, flag off)

Apply this diff to `offpath_fixture/pricing.py` (do NOT commit):

```diff
-    print(f"[v2] refund {net} cents in {currency}")
+    # S1: attempt to handle JPY here
+    if currency == "JPY":
+        net = int(net * 0.95)
+    print(f"[v2] refund {net} cents in {currency} (s1)")
```

Then run twice (two attempts editing only pricing.py; between attempts,
change `(s1)` to `(s1b)` so the second attempt has a different diff):

```bash
python spike/offpath_spike.py run -- pytest tests/test_refund.py -x
# edit (s1) -> (s1b)
python spike/offpath_spike.py run -- pytest tests/test_refund.py -x
```

Expected on attempt #2 (and #3): `SAME_FAILURE`, evidence `high`,
verdict `NO_OBSERVED_SIGNAL`, observed `0/N` changed lines.

Now revert: `git checkout -- offpath_fixture/pricing.py`

## 3. S2: on-path edit (legacy_processor.py)

Apply (do NOT commit):

```diff
-        print(f"[legacy] rejecting currency {currency}")
+        print(f"[legacy] rejecting currency {currency} (s2: on-path edit)")
```

```bash
python spike/offpath_spike.py run -- pytest tests/test_refund.py -x
```

Expected: `changed_observed > 0` (the edited print line executes),
state `SAME_FAILURE` or `FAILURE_CHANGED` depending on normalization
(record actual).

## 4. S3: partial fix -> failure moves deeper

Extend the edit (do NOT commit):

```diff
-    if currency not in SUPPORTED_CURRENCIES:
-        # S2 edits the print below; the raise must stay on the same line.
-        print(f"[legacy] rejecting currency {currency} (s2: on-path edit)")
-        raise ValueError("invalid currency")
+    if currency not in SUPPORTED_CURRENCIES:
+        print(f"[legacy] rejecting currency {currency} (s3)")
+        if currency != "JPY":
+            raise ValueError("invalid currency")
+    amount = item["price_cents"] * order.get("quantity", 1)
+    fee = rates.refund_fee_cents(amount)
+    settlement = SETTLEMENT_ACCOUNTS[currency]   # KeyError for JPY: deeper failure
+    return {
+        "sku": sku,
+        "refund_cents": amount - fee,
+        "settlement_account": settlement,
+        "processor": "legacy",
+    }
```

(Remove the now-duplicated tail of the original function.)

```bash
python spike/offpath_spike.py run -- pytest tests/test_refund.py -x
```

Expected: `FAILURE_CHANGED (old -> new)` with the new signature being a
`KeyError` at the `SETTLEMENT_ACCOUNTS` line.

Now revert: `git checkout -- offpath_fixture/legacy_processor.py`

## 5. S4: return to a prior state

Re-apply the EXACT S1b diff to `pricing.py` (same content as the second
S1 attempt: `(s1b)`), then:

```bash
python spike/offpath_spike.py run -- pytest tests/test_refund.py -x
```

Expected: `RETURNED_TO_PRIOR_STATE (attempt #N)` referencing the S1b
attempt (same diff_hash + cmd + signature triple).

Then revert: `git checkout -- offpath_fixture/pricing.py`

## 6. S5: subprocess (no visibility) + control

```bash
python spike/offpath_spike.py run -- pytest tests/test_subprocess_refund.py -x
python spike/offpath_spike.py run -- pytest tests/test_control_catalog.py -x
```

Expected: subprocess run -> `UNKNOWN` with `INSUFFICIENT_EXECUTION_EVIDENCE`
and reachability withheld; control run -> `RESOLVED`, NOT `UNKNOWN`.

## 7. Verification and ledger

```bash
python spike/offpath_spike.py verify    # re-derives every event from raw artifacts
python spike/offpath_spike.py ledger    # prints the S1-S5 pass/fail table
git add .offpath && git commit -m "Spike evidence: S1-S5 timeline"
```

`verify` must print PASS for every attempt before the ledger counts.

## 8. Overhead measurement (same machine, same env, sequential)

```bash
for i in 1 2 3 4 5; do /usr/bin/time -f "plain %e" pytest tests/test_refund.py -x 2>&1 | tail -1; done
for i in 1 2 3 4 5; do /usr/bin/time -f "wrapped %e" python spike/offpath_spike.py run -- pytest tests/test_refund.py -x >/dev/null 2>timing.txt; tail -1 timing.txt; done
```

(On macOS use `time` builtin and copy the real time.) Record medians and
the multiplier in the report. Informational only; no optimization.

## 9. Fill in spike/REPORT.md

Paste: baseline number, per-scenario actual state + JSONL event excerpt,
verify output, ledger output, overhead numbers, and any model breakage
observed. Commit and push.
