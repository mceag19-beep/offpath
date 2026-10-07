# Contributing to OffPath

OffPath is a focused evidence engine: every run must stay traceable from
its summary line back to raw artifacts. Contributions that preserve that
property are welcome; scope expansion (new runners, languages, UIs,
telemetry, AI layers) needs prior discussion via an issue.

## Setup

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# POSIX:
# source .venv/bin/activate
pip install -e ".[dev]"
```

Requires git. Python 3.10+.

## Checks (run all before a PR)

```bash
python -m pytest -q
```

The suite (`tests_offpath/`) builds a real S1–S5 timeline against the
fixture app in `offpath_fixture/` with an isolated `OFFPATH_DIR`, so your
own `.offpath/` history is never touched. Fixture sources mutated
mid-suite are restored afterwards; `git status` should show no fixture
modifications when the run finishes.

Measure coverage overhead only when run performance changes:

```bash
python scripts/measure_overhead.py
```

## Rules

- Preserve the evidence model: no causality claims, `UNKNOWN` stays
  first-class, `FAILURE_CHANGED` means changed evidence, not progress.
- Every code change needs a test that would fail without it.
- Every derived claim must stay re-derivable from raw run artifacts.
- Keep the CLI output terse and evidence-oriented; document exit codes.
- Do not add network calls, telemetry, or new data collection.
