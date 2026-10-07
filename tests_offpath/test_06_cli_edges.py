"""CLI failure-mode tests: the tool must fail clearly and safely.

No silent corruption, no misleading success output: outside a git repo,
with a corrupt timeline, or with an unrunnable command, offpath exits
non-zero on stderr and records nothing.
"""

import json
import os
import subprocess
import sys

from tests_offpath.conftest import ROOT, cli


def _run_cli(args, cwd, offpath_dir):
    env = dict(os.environ, OFFPATH_DIR=str(offpath_dir))
    proc = subprocess.run(
        [sys.executable, "-m", "offpath", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc


def test_run_outside_git_repo_refuses(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    state = tmp_path / "state"
    proc = _run_cli(
        ["run", "--", sys.executable, "-m", "pytest", "--version"],
        cwd=plain,
        offpath_dir=state,
    )
    assert proc.returncode == 2
    assert "not inside a git repository" in proc.stderr
    assert "[offpath] attempt" not in proc.stdout
    assert not (state / "events.jsonl").exists()


def test_status_outside_git_repo_still_works(tmp_path):
    # status only reads the timeline; repo presence is not required.
    state = tmp_path / "state"
    proc = _run_cli(["status"], cwd=tmp_path, offpath_dir=state)
    assert proc.returncode == 0
    assert "no attempts recorded" in proc.stdout


def test_corrupt_timeline_status_fails_clearly(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "events.jsonl").write_text("NOT JSON{{{\n", encoding="utf-8")
    proc = _run_cli(["status", "--json"], cwd=ROOT, offpath_dir=state)
    assert proc.returncode == 2
    assert "corrupt timeline" in proc.stderr


def test_corrupt_timeline_run_records_nothing(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    before = "NOT JSON{{{\n"
    (state / "events.jsonl").write_text(before, encoding="utf-8")
    proc = _run_cli(
        ["run", "--", sys.executable, "-m", "pytest", "--version"],
        cwd=ROOT,
        offpath_dir=state,
    )
    assert proc.returncode == 2
    assert "corrupt timeline" in proc.stderr
    assert (state / "events.jsonl").read_text(encoding="utf-8") == before


def test_missing_command_binary_exit_127(tmp_path):
    proc = _run_cli(
        ["run", "--", "offpath-no-such-binary-xyz"],
        cwd=ROOT,
        offpath_dir=tmp_path / "state",
    )
    assert proc.returncode == 127
    assert "command not found" in proc.stdout


def test_help_version_unknown_command(tmp_path):
    state = tmp_path / "state"
    proc = _run_cli(["--help"], cwd=ROOT, offpath_dir=state)
    assert proc.returncode == 0 and "usage:" in proc.stdout
    proc = _run_cli(["--version"], cwd=ROOT, offpath_dir=state)
    assert proc.returncode == 0 and "offpath" in proc.stdout
    proc = _run_cli(["frobnicate"], cwd=ROOT, offpath_dir=state)
    assert proc.returncode == 2 and "unknown command" in proc.stderr


def test_usage_errors_go_to_stderr(tmp_path):
    proc = _run_cli(["run"], cwd=ROOT, offpath_dir=tmp_path / "state")
    assert proc.returncode == 2
    assert "usage" in proc.stderr
    assert proc.stdout == ""


def test_status_json_survives_unicode_output(tmp_path, monkeypatch):
    # Unicode in test output must not break artifact writes (utf-8).
    from offpath import runner

    monkeypatch.setenv("OFFPATH_DIR", str(tmp_path / "state"))
    event, _ = runner.do_run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            "print('héllo wörld ✓'); raise SystemExit(3)",
        ],
        root=ROOT,
    )
    assert event["exit_code"] == 3
    raw = (tmp_path / "state" / "runs" / "001" / "output.txt").read_text(
        encoding="utf-8"
    )
    assert "héllo" in raw


def test_events_jsonl_is_valid_json_per_line(tmp_path, monkeypatch):
    from offpath import runner

    monkeypatch.setenv("OFFPATH_DIR", str(tmp_path / "state"))
    runner.do_run(
        [sys.executable, "-m", "pytest", "tests/test_control_catalog.py", "-x"],
        root=ROOT,
    )
    for line in (tmp_path / "state" / "events.jsonl").read_text().splitlines():
        assert json.loads(line)["attempt"] == 1
