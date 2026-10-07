"""Overhead measurement: plain pytest vs offpath-wrapped (spike methodology).

Same command, same environment, sequential runs; compares wall-clock
medians and reports the multiplier. Wrapped runs use a TEMP OFFPATH_DIR
so the developer's timeline is untouched. Informational only: if
overhead is high, report it rather than silently changing semantics.
Targeted-test-only coverage is the intended MVP usage model.
"""

import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
CMD = [PY, "-m", "pytest", "tests/test_refund.py", "-x"]
N = 5


def time_cmd(cmd, env):
    start = time.perf_counter()
    subprocess.run(cmd, cwd=ROOT, capture_output=True, env=env)
    return time.perf_counter() - start


def main():
    env = dict(os.environ)
    plain = sorted(time_cmd(CMD, env) for _ in range(N))
    with tempfile.TemporaryDirectory(prefix="offpath-overhead-") as tmp:
        env["OFFPATH_DIR"] = tmp
        wrapped = sorted(
            time_cmd([PY, "-m", "offpath", "run", "--", *CMD], env)
            for _ in range(N)
        )
    mp, mw = statistics.median(plain), statistics.median(wrapped)
    print(f"plain pytest runs (s):   {[round(t, 3) for t in plain]}")
    print(f"offpath-wrapped (s):     {[round(t, 3) for t in wrapped]}")
    print(f"median plain:   {mp:.3f}s")
    print(f"median wrapped: {mw:.3f}s")
    print(f"multiplier:     {mw / mp:.2f}x")


if __name__ == "__main__":
    main()
