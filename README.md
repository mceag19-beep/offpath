# OffPath — did your debugging attempt produce evidence?

> OffPath tells you whether your debugging attempt produced observable
> evidence, or whether you are repeating a hypothesis the test cannot see.

You change some code, re-run the failing test, it still fails. Did your
edit even execute — or did you just test the same hypothesis twice?
OffPath wraps your test command, records every attempt in an append-only
timeline, and reports, with receipts, whether changed lines were observed
executing.

OffPath is an **evidence engine, not a causality oracle**. It never claims
an edit cannot affect a failure or is unrelated to it. Coverage demonstrates
execution evidence, not causality.

```text
$ offpath run -- pytest tests/test_refund.py -x
FAILED tests/test_refund.py::test_refund - ValueError: invalid currency
[offpath] attempt #1 | NO_BASELINE | signature b3d18b29
[offpath] observed execution: no working-tree changes recorded
[offpath] evidence: high | 133 executed lines
```

Edit an off-path file and re-run: same failure, zero changed lines
observed, and OffPath says so plainly instead of letting you burn a third
attempt on the same invisible hypothesis:

```text
[offpath] attempt #2 | SAME_FAILURE | signature b3d18b29
[offpath] observed execution: 0 of 14 changed lines recorded
[offpath] evidence: high | 133 executed lines
[offpath] this hypothesis has produced no observed signal
```

## Who is it for

Developers debugging failing tests in Python/pytest projects, and coding
agents that need a machine-readable debugging history
(`offpath status --json`) instead of parsing terminal text.

## Install

```bash
git clone <repo-url> && cd offpath
pip install -e .          # users
pip install -e ".[dev]"   # contributors (also installs pytest)
```

Requires Python 3.10+, pytest, coverage.py, git. Verify with
`offpath --version` and `python -m pytest -q` (28+ tests, real timeline,
isolated from your own `.offpath/`).

## Usage

```text
offpath run -- pytest tests/test_refund.py -x
offpath status
offpath status --json
offpath run --gate N -- pytest tests/test_refund.py -x
```

Each `offpath run` execution becomes one immutable debugging attempt:
appended to `.offpath/events.jsonl` with raw artifacts under
`.offpath/runs/NNN/` (command, stdout/stderr, exit code, diff, coverage
data, environment fingerprint, signature inputs, derived state). Your
`.offpath/` directory is local state — it is git-ignored and never
uploaded anywhere (OffPath makes no network connections at all).

## What each run answers

1. What code state was tested? (`git diff -U0 HEAD` ranges + diff hash)
2. What command was run?
3. What failure signature occurred? (exception type + normalized
   message template + frame-chain identity; raw traceback preserved)
4. What execution evidence was observed? (changed lines observed /
   not observed / on stack — only when evidence quality allows)
5. Did the attempt repeat a previous recorded state?
6. Did the failure change?
7. Was visibility sufficient for a reachability observation?

## States (the timeline spine works even without usable coverage)

| State | Meaning |
|---|---|
| `NO_BASELINE` | First relevant run; no previous comparable failure. |
| `SAME_FAILURE` | Same normalized failure signature as the previous failure. |
| `FAILURE_CHANGED` | The observed failure signature changed — new failure evidence was observed. This does NOT mean progress was made. |
| `RESOLVED` | The command succeeds where a failure was tracked. |
| `RETURNED_TO_PRIOR_STATE` | The recorded (diff identity, command, failure signature) tuple matches a previous attempt; the output names that attempt (e.g. "matches recorded diff, command, and failure signature of attempt #2"). The identity is intentionally limited — it does not capture environment/dependency state. |
| `UNKNOWN` | Execution visibility was insufficient for a reachability observation. Reachability observations are withheld, but failure-signature timeline tracking stays active. |

## Evidence quality (independent from state)

`high` — genuine measured execution (coverage footprint at/above the
provisional threshold). `medium` — below the coverage threshold, but
measured project traceback frames for files with measured execution.
`low` — neither. High evidence requires measured
execution information; traceback text embedded in output never counts.

`measured_frames` (a `File "…", line N` token starting its line) are
execution evidence — provided the file shows measured execution in the
run's coverage. A line-start frame for a file with zero executed lines is
indistinguishable from transported text, so it is conservatively treated
as embedded. `embedded_frames` (project frames quoted inside
transported text, e.g. a child process's stderr inside a parent assertion
message) are text, not execution, and never count as visibility.

`UNKNOWN` requires BOTH: (A) no meaningful visibility source (near-empty
coverage AND no measured project frames), AND (B) an anomaly relative to
expectations (below a provisional fraction of the prior high-evidence
reference total, or a real failure with ~nothing observed and no reference
yet). A legitimate high-evidence run with zero changed-line intersection is
`NO_OBSERVED_SIGNAL`, never `UNKNOWN`. A passing run is `RESOLVED`, never
`UNKNOWN`. Thresholds are provisional spike scaffolding, isolated in
`src/offpath/config.py` for later refinement.

Neutral verdicts: `NO_OBSERVED_SIGNAL` ("this hypothesis has produced no
observed signal") and `INSUFFICIENT_EXECUTION_EVIDENCE` (visibility
insufficient; reachability withheld). Every derived claim is re-derivable:
signatures from raw traceback + `signature_inputs`, intersections from
diff + executed lines, returned-state matches from recorded attempt fields.

## Exit codes (`offpath run`)

| Code | Meaning |
|---|---|
| 0 | wrapped command succeeded |
| 1 | wrapped command failed (its exit code propagates when no override applies) |
| 2 | `--gate N`: N consecutive no-signal attempts |
| 3 | `RETURNED_TO_PRIOR_STATE` (with or without `--gate`) |

`FAILURE_CHANGED` is not success; `RESOLVED` is not just another failure.
Exit 2/3 take precedence over the command's own code: keep gate runs to
test commands, since a command exiting 2/3 itself is indistinguishable
from a gate signal.

`offpath status --json` is the stable machine-readable contract
(`{offpath, count, attempts, last}`); agents consume it, never CLI text.

## Measured overhead (same machine, same env, sequential)

- Plain `pytest tests/test_refund.py -x`, 5 runs, median: **0.703 s**
- Wrapped `offpath run`, 5 runs, median: **1.744 s**
- Multiplier: **2.48x**

Reported, not optimized. Targeted-test-only coverage is the intended MVP
usage model. Reproduce with `python scripts/measure_overhead.py` (uses a
temp timeline; your `.offpath/` is untouched).

## Known limitations (documented, not solved)

- Signature normalization is regex-based (hex/UUID/timestamp collapsing)
  and fragile against arbitrary interpolated values in messages.
- `RETURNED_TO_PRIOR_STATE` uses the limited recorded tuple only; it
  ignores environment, dependency, database, and untracked-file state.
- Untracked files are invisible to diff tracking; pure deletions
  contribute no observable lines.
- Visibility thresholds (`config.py`) are provisional spike scaffolding.
- Only pytest + coverage.py + git are supported; other runners/languages
  need new adapters behind the existing module boundaries.
- Subprocess coverage requires out-of-band setup (e.g.
  `COVERAGE_PROCESS_START`); without it, child execution is UNKNOWN by
  design, not a bug.
- `conftest.py` files, `tests/`, `spike/`, and tooling dirs are excluded
  from project execution evidence by construction.
- Environment fingerprint (`env_fingerprint`) is an interpretive aid, not
  a complete reproducibility fingerprint.
- Gate exits 2/3 mask a wrapped command's own 2/3 exit codes.
- Child output is decoded as UTF-8 (undecodable bytes become U+FFFD);
  signatures are deterministic for identical child bytes on any machine.
- OffPath refuses to run outside a git repository (diff tracking would be
  meaningless); a corrupt timeline fails loudly instead of appending.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports: use the issue
template. Security notes: see [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE.md](LICENSE.md). Fill in the copyright holder before
redistribution if it is still marked as a placeholder.
