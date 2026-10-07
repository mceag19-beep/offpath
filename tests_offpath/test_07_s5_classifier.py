"""S5 classifier regression tests (no git/coverage/pytest rendering needed).

Pins the exact contract that clean-CI failures showed was load-bearing:
child/subprocess frames transported inside a parent assertion message must
classify as EMBEDDED (never measured), so the visibility rules still yield
UNKNOWN. A pre-fix classifier that lumps every project frame into
`measured` flips S5 to FAILURE_CHANGED — this module fails on such code.
"""

from pathlib import Path

import pytest

from offpath import evidence as evidence_module
from offpath.traceback_parse import parse_traceback

ROOT = Path("/repo")

# Hand-built minimal S5 shape: parent assertion message transporting a
# child's native traceback. No pytest rendering involved.
S5_SHAPED = """\
============================= test session starts =============================
tests/test_subprocess_refund.py F
================================== FAILURES ===================================
___________________________ test_refund_subprocess ____________________________
>       assert result.returncode == 0, result.stderr
E       AssertionError: Traceback (most recent call last):
E           File "<frozen runpy>", line 198, in _run_module_as_main
E           File "/repo/offpath_fixture/subprocess_entry.py", line 17, in <module>
E             main()
E           File "/repo/offpath_fixture/checkout.py", line 26, in process_refund
E             return legacy_processor.refund(order)
E           File "/repo/offpath_fixture/legacy_processor.py", line 25, in refund
E             raise ValueError("invalid currency")
E         ValueError: invalid currency
E
E       assert 1 == 0
"""


def test_s5_shaped_output_classifies_embedded_only():
    exc, msg, measured, embedded = parse_traceback(S5_SHAPED, ROOT)
    assert exc == "AssertionError"
    assert measured == []
    assert embedded == [
        "offpath_fixture/subprocess_entry.py:17:<module>",
        "offpath_fixture/checkout.py:26:process_refund",
        "offpath_fixture/legacy_processor.py:25:refund",
    ]


@pytest.mark.parametrize("reference", [None, 1, 133, 10_000])
def test_s5_shaped_output_is_unknown_for_any_reference(reference):
    exc, _msg, measured, _embedded = parse_traceback(S5_SHAPED, ROOT)
    assert evidence_module.visibility_unknown(1, exc, 0, measured, reference) is True
    assert evidence_module.evidence_grade(0, measured) == "low"


def test_lumping_frames_into_measured_breaks_unknown():
    # Documents WHY the measured/embedded split exists: feed the embedded
    # frames back as if they were measured (the pre-fix behavior) and the
    # S5 shape stops being UNKNOWN.
    _exc, _msg, _measured, embedded = parse_traceback(S5_SHAPED, ROOT)
    assert embedded, "need transported frames for this regression check"
    assert (
        evidence_module.visibility_unknown(1, "AssertionError", 0, embedded, 133)
        is False
    )


def test_bare_file_token_at_output_start_is_measured():
    # rfind edge: a File token at position 0 has an empty prefix, which
    # counts as a line start (native-traceback shape, not S5 transport).
    out = 'File "/repo/offpath_fixture/checkout.py", line 26, in process_refund\n'
    _exc, _msg, measured, embedded = parse_traceback(out, ROOT)
    assert measured == ["offpath_fixture/checkout.py:26:process_refund"]
    assert embedded == []


def test_bare_frame_without_coverage_support_is_not_measured():
    # The CI failure shape: a line-start project frame whose file shows
    # zero executed lines in this run's coverage is transported text, not
    # execution evidence — it must not defeat the UNKNOWN rules.
    out = 'File "/repo/offpath_fixture/checkout.py", line 26, in process_refund\n'
    exc, _msg, measured, embedded = parse_traceback(out, ROOT, executed={})
    assert measured == []
    assert embedded == ["offpath_fixture/checkout.py:26:process_refund"]
    assert evidence_module.visibility_unknown(1, exc, 0, measured, 133) is True


def test_bare_frame_with_coverage_support_stays_measured():
    # The same line-start frame IS measured when its file demonstrably
    # executed in this run: the cross-check is one-directional and cannot
    # fabricate evidence, only validate it.
    out = 'File "/repo/offpath_fixture/checkout.py", line 26, in process_refund\n'
    _exc, _msg, measured, embedded = parse_traceback(
        out, ROOT, executed={"offpath_fixture/checkout.py": [15, 26]}
    )
    assert measured == ["offpath_fixture/checkout.py:26:process_refund"]
    assert embedded == []
