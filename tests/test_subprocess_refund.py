"""S5 scenario: the failing flow runs in a child process.

The child raises ValueError; the parent sees only a failed assertion
whose message embeds the child's stderr. Coverage in the parent has no
visibility into offpath_fixture (the child is not measured), so the
spike must report UNKNOWN with reachability withheld, driven by the
visibility rules and NOT merely by empty intersection.

Deliberately imports nothing from offpath_fixture at module level so
the parent run records near-zero fixture lines.
"""

import os
import subprocess
import sys


def test_refund_subprocess():
    env = dict(os.environ, REFUND_V2="off")
    result = subprocess.run(
        [sys.executable, "-m", "offpath_fixture.subprocess_entry"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
