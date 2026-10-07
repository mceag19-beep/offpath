# Security policy

OffPath is a strictly local developer tool:

- No network access. The implementation makes no outbound connections,
  sends no telemetry, uploads no source code, and contacts no external
  services. (Verified by audit: no socket/HTTP/requests usage anywhere in
  `src/`, `scripts/`, or the test suite.)
- No credentials are collected. Run artifacts under `.offpath/runs/`
  store the wrapped command's stdout/stderr, the working-tree diff,
  coverage data, and environment versions — so do not paste secrets into
  commands you wrap, and do not publish your `.offpath/` directory
  (it is git-ignored by default).
- OffPath never modifies your repository except by appending its own
  timeline (`.offpath/events.jsonl`) and run artifacts. It never edits,
  stages, or commits your source files.
- Subprocess execution is list-form only (no shell); the wrapped command
  is exactly what you typed after `--`.

## Reporting a vulnerability

Open a GitHub issue titled `[security]` describing the concern and how to
reproduce it. Do not include secrets, credentials, or private repository
contents in the report.
