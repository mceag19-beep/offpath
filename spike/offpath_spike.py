#!/usr/bin/env python3
"""OffPath spike: record each test run as an auditable experiment.

Commands:
  baseline -- <cmd...>  record a clean-tree reference run
  run      -- <cmd...>  wrap a run: diff + coverage + signature + state
  verify                re-derive every event from raw stored evidence
  ledger                print the S1-S5 pass/fail table

IMPORTANT: thresholds in _visibility_unknown() (10% of baseline,
< 20 executed lines) are SPIKE SCAFFOLDING ONLY to test the UNKNOWN
hypothesis. They are provisional and are NOT final product logic.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / ".offpath"
EVENTS = STATE_DIR / "events.jsonl"
RUNS_DIR = STATE_DIR / "runs"
BASELINE_FILE = STATE_DIR / "baseline.json"
SOURCE_PREFIX = "offpath_fixture"


def sha(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:8]


def load_events():
    if not EVENTS.exists():
        return []
    return [json.loads(l) for l in EVENTS.read_text().splitlines() if l.strip()]


def append_event(ev):
    STATE_DIR.mkdir(exist_ok=True)
    with EVENTS.open("a") as f:
        f.write(json.dumps(ev) + "\n")


def load_baseline():
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text())
    return None


# ---------------------------------------------------------------- diff

def changed_lines():
    """Parse `git diff -U0` into {relpath: [[start, end], ...]} (1-indexed).

    Also covers unstaged + staged changes; untracked files are ignored
    (documented spike limitation).
    """
    out = subprocess.run(
        ["git", "diff", "-U0", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout
    result, current = {}, None
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            current = line[len("+++ b/"):]
            result.setdefault(current, [])
        elif line.startswith("@@") and current:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2) or 1)
                if count > 0:  # pure deletions have count 0: nothing to observe
                    result[current].append([start, start + count - 1])
    diff_hash = sha(out) if out.strip() else sha("")
    return result, diff_hash, out


# ------------------------------------------------------------ traceback

def parse_traceback(output: str):
    """Returns (exc_type, message, measured_frames, embedded_frames).

    measured_frames: frames from the PARENT's own traceback (the 'File'
    token starts a traceback line). embedded_frames: frames quoted inside
    transported text (child stderr in an assert message) - text, not
    measured execution; never counts as visibility (S5).
    """
    exc_type, message = None, None
    m = re.search(r"^E\s+(\w+(?:\.\w+)*):\s*(.*)$", output, re.M)
    if m:
        exc_type, message = m.group(1), m.group(2)
    if exc_type is None:
        m = re.search(r"^(\w+(?:Error|Exception|Exit|Interrupt|Warning)):\s*(.*)$", output, re.M)
        if m:
            exc_type, message = m.group(1), m.group(2)
    if exc_type is None:
        m = re.search(r"(AssertionError):\s*(assert[^\n]*)", output)
        if m:
            exc_type, message = m.group(1), m.group(2)

    measured, embedded = [], []
    for fm in re.finditer(r'File "([^"]+)", line (\d+)(?:, in ([\w<>]+))?', output):
        path, lineno, func = fm.group(1), int(fm.group(2)), fm.group(3) or "?"
        norm = path.replace("\\\\", "/")
        if SOURCE_PREFIX not in norm:
            continue
        rel = norm[norm.index(SOURCE_PREFIX):]
        entry = f"{rel}:{lineno}:{func}"
        line_start = output.rfind("\n", 0, fm.start()) + 1
        if output[line_start:fm.start()].strip() == "":
            measured.append(entry)
        else:
            embedded.append(entry)

    if message is not None:
        message = re.sub(r"0x[0-9a-fA-F]+", "<hex>", message)
        message = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", message)
        message = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?", "<ts>", message)
        message = re.sub(r"([\w./\\-]*offpath-spike[\\/])", "<root>/", message)
        message = message.replace("\\\\n", " ").replace("\\n", " ").strip()
    return exc_type, message, measured, embedded


def make_signature(exc_type, message, frames):
    inputs = {"exception": exc_type, "message_template": message, "frames": frames}
    return sha(json.dumps(inputs, sort_keys=True)), inputs


# -------------------------------------------------------------- coverage

def run_under_coverage(cmd):
    """Run cmd under coverage.py out-of-process; returns (exit, output, executed)."""
    import coverage

    start = time.time()
    
    cov_cmd = [sys.executable, "-m", "coverage", "run", "--source", SOURCE_PREFIX, "--data-file", str(STATE_DIR / ".coverage.tmp")]
    if cmd[0] == "pytest":
        cov_cmd.extend(["-m", "pytest"] + cmd[1:])
    else:
        cov_cmd.extend(cmd)
        
    proc = subprocess.run(cov_cmd, cwd=ROOT, capture_output=True, text=True)
    wall = time.time() - start
    
    cov = coverage.Coverage(data_file=str(STATE_DIR / ".coverage.tmp"))
    cov.load()
    
    executed, total = {}, 0
    for f in cov.get_data().measured_files():
        if SOURCE_PREFIX in f.replace("\\", "/"):
            lines = sorted(cov.get_data().lines(f) or [])
            rel_f = os.path.relpath(f, ROOT).replace("\\", "/")
            executed[rel_f] = lines
            total += len(lines)
    (STATE_DIR / ".coverage.tmp").unlink(missing_ok=True)
    return proc.returncode, proc.stdout + proc.stderr, executed, total, wall


# ---------------------------------------------------------------- states

def evidence_grade(total_lines, frames):
    """high: coverage plausible; medium: frames only; low: neither."""
    if total_lines >= 20:  # PROVISIONAL spike scaffolding threshold
        return "high"
    if frames:
        return "medium"
    return "low"


def visibility_unknown(exit_code, exc_type, executed_total, measured_frames, baseline):
    """UNKNOWN requires BOTH no visibility source AND an anomaly.

    Frames embedded in transported text are NOT visibility.
    Never fires for exit==0 or for high-evidence runs with legitimate
    zero intersection. PROVISIONAL thresholds; see module docstring.
    """
    no_source = executed_total < 20 and not measured_frames
    if not no_source or exit_code == 0:
        return False
    if baseline:
        anomaly = executed_total < 0.10 * baseline["total_executed_lines"]
    else:
        anomaly = exc_type is not None  # real failure ran but we saw ~nothing
    return anomaly


def compute_state(exit_code, signature, diff_hash, cmd_str, events, unknown):
    if unknown:
        return "UNKNOWN"
    if exit_code == 0:
        return "RESOLVED"
    for prev in reversed(events):
        if (
            prev["diff_hash"] == diff_hash
            and prev["cmd"] == cmd_str
            and prev["signature"] == signature
        ):
            return f"RETURNED_TO_PRIOR_STATE (attempt #{prev['attempt']})"
    failing = [e for e in events if e["signature"]]
    if not failing:
        return "NO_BASELINE"
    if failing[-1]["signature"] == signature:
        streak = 1
        for e in reversed(failing[:-1]):
            if e["signature"] == signature:
                streak += 1
            else:
                break
        return f"SAME_FAILURE (x{streak})"
    return f"FAILURE_CHANGED ({failing[-1]['signature']} -> {signature})"


def intersect(changed, executed, frame_files):
    obs, not_obs, on_stack = 0, 0, 0
    for f, ranges in changed.items():
        ex = set(executed.get(f, []))
        for start, end in ranges:
            for ln in range(start, end + 1):
                if ln in ex:
                    obs += 1
                else:
                    not_obs += 1
                if f in frame_files:
                    on_stack += 1
    return obs, not_obs, on_stack


# ---------------------------------------------------------------- commands

def do_run(cmd, is_baseline=False):
    STATE_DIR.mkdir(exist_ok=True)
    RUNS_DIR.mkdir(exist_ok=True)
    events = load_events()
    attempt = len(events) + 1
    changed, diff_hash, raw_diff = changed_lines()
    exit_code, output, executed, total, wall = run_under_coverage(cmd)
    exc_type, message, measured_frames, embedded_frames = parse_traceback(output)
    frames = measured_frames
    signature, sig_inputs = make_signature(exc_type, message, frames)
    if exit_code == 0:
        signature = None
    cmd_str = " ".join(cmd)

    run_dir = RUNS_DIR / f"{attempt:03d}"
    run_dir.mkdir(exist_ok=True)
    (run_dir / "output.txt").write_text(output)
    (run_dir / "diff.patch").write_text(raw_diff)
    (run_dir / "executed.json").write_text(json.dumps(executed, indent=1))

    if is_baseline:
        BASELINE_FILE.write_text(json.dumps(
            {"cmd": cmd_str, "total_executed_lines": total,
             "executed_lines": executed}, indent=1))
        print(f"[offpath] baseline recorded: {total} executed lines")
        return 0

    baseline = load_baseline()
    frame_files = {fr.rsplit(":", 2)[0] for fr in frames}
    obs, not_obs, on_stack = intersect(changed, executed, frame_files)
    unknown = visibility_unknown(exit_code, exc_type, total, measured_frames, baseline)
    evidence = evidence_grade(total, measured_frames)
    state = compute_state(exit_code, signature, diff_hash, cmd_str, events, unknown)

    verdicts = []
    if unknown:
        verdicts.append("INSUFFICIENT_EXECUTION_EVIDENCE")
    elif exit_code != 0 and changed and obs == 0 and evidence == "high":
        verdicts.append("NO_OBSERVED_SIGNAL")

    env = {
        "python": sys.version.split()[0],
        "REFUND_V2": os.environ.get("REFUND_V2"),
        "pytest": _pkg_version("pytest"),
    }
    event = {
        "attempt": attempt, "cmd": cmd_str, "env_fingerprint": env,
        "diff_hash": diff_hash, "changed_lines": changed,
        "raw_traceback": output[-3000:],
        "normalized_message": message, "frame_chain": frames,
        "embedded_frames": embedded_frames,
        "signature": signature, "signature_inputs": sig_inputs,
        "coverage": {
            "executed_lines": executed, "total_executed_lines": total,
            "baseline_executed_lines": (baseline or {}).get("total_executed_lines"),
            "collector": "coverage.py",
        },
        "intersection": {"changed_observed": obs,
                         "changed_not_observed": not_obs,
                         "changed_on_stack": on_stack},
        "evidence": evidence, "state": state, "verdicts": verdicts,
        "wall_seconds": round(wall, 3), "exit_code": exit_code,
        "artifacts": {"output": str(run_dir / "output.txt"),
                      "diff": str(run_dir / "diff.patch"),
                      "executed": str(run_dir / "executed.json")},
    }
    append_event(event)
    print(output, end="")
    sig = signature or "-"
    print(f"[offpath] attempt #{attempt} | {state} | sig {sig} | "
          f"evidence: {evidence} | observed {obs}/{obs + not_obs} changed lines")
    for v in verdicts:
        print(f"[offpath] verdict: {v}")
    return exit_code


def _pkg_version(name):
    try:
        import importlib.metadata
        return importlib.metadata.version(name)
    except Exception:
        return "unknown"


def do_verify():
    """Re-derive each event from raw stored artifacts; report mismatches."""
    ok = True
    for ev in load_events():
        n = ev["attempt"]
        raw = Path(ev["artifacts"]["output"]).read_text()
        exc, msg, frames, _embedded = parse_traceback(raw)
        sig, inputs = make_signature(exc, msg, frames)
        if ev["exit_code"] == 0:
            sig = None
        stored_exec = json.loads(Path(ev["artifacts"]["executed"]).read_text())
        checks = {
            "signature_recomputable": sig == ev["signature"],
            "signature_inputs_match": inputs == ev["signature_inputs"],
            "executed_matches_event": stored_exec == ev["coverage"]["executed_lines"],
            "raw_traceback_tail": ev["raw_traceback"] == raw[-3000:],
        }
        bad = [k for k, v in checks.items() if not v]
        status = "OK" if not bad else f"MISMATCH: {bad}"
        if bad:
            ok = False
        print(f"attempt #{n}: {status}")
    print("VERIFY: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def do_ledger():
    """Print the S1-S5 pass/fail table from the recorded timeline."""
    events = load_events()
    rows = []

    def find(pred):
        return next((e for e in events if pred(e)), None)

    s1 = find(lambda e: "NO_OBSERVED_SIGNAL" in e["verdicts"]
              and "SAME_FAILURE" in e["state"])
    rows.append(("S1", "SAME_FAILURE + NO_OBSERVED_SIGNAL, observed=0",
                 s1 and s1["intersection"]["changed_observed"] == 0
                 and s1["evidence"] == "high"))
    s2 = find(lambda e: e["intersection"]["changed_observed"] > 0
              and e["exit_code"] != 0)
    rows.append(("S2", "changed_observed > 0", bool(s2)))
    s3 = find(lambda e: e["state"].startswith("FAILURE_CHANGED"))
    rows.append(("S3", "FAILURE_CHANGED with old->new signatures", bool(s3)))
    s4 = find(lambda e: e["state"].startswith("RETURNED_TO_PRIOR_STATE"))
    rows.append(("S4", "RETURNED_TO_PRIOR_STATE with attempt ref", bool(s4)))
    s5 = find(lambda e: e["state"] == "UNKNOWN")
    s5ok = bool(s5) and "INSUFFICIENT_EXECUTION_EVIDENCE" in s5.get("verdicts", [])
    ctrl_bad = any(
        e["state"] == "UNKNOWN" and e["exit_code"] == 0 for e in events
    )
    rows.append(("S5", "UNKNOWN (visibility rules) + control not UNKNOWN",
                 s5ok and not ctrl_bad))

    print("| Scenario | Expected | Pass |")
    print("|----------|----------|------|")
    for name, exp, passed in rows:
        print(f"| {name} | {exp} | {'PASS' if passed else 'FAIL'} |")
    allpass = all(p for _, _, p in rows)
    print("LEDGER: " + ("GREEN" if allpass and len(events) >= 5 else "RED"))
    return 0 if allpass else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd in ("run", "baseline"):
        if "--" in argv:
            test_cmd = argv[argv.index("--") + 1:]
        else:
            test_cmd = argv[2:]
        if not test_cmd:
            print("usage: offpath_spike.py run -- <cmd...>")
            return 2
        return do_run(test_cmd, is_baseline=(cmd == "baseline"))
    if cmd == "verify":
        return do_verify()
    if cmd == "ledger":
        return do_ledger()
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
