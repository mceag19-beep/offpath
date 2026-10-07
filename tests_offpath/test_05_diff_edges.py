"""Diff-parser regression tests (pure unit tests, no git needed).

Covers the boundary shapes `git diff -U0 HEAD` can produce, including the
two real bugs found in audit: trailing-tab pathnames and C-quoted
(non-ASCII / space) pathnames, the latter of which previously misattributed
hunks to the wrong file.
"""

import subprocess

import pytest

from offpath import diffs
from offpath.diffs import GitError, parse_diff_text


def test_space_path_with_trailing_tab():
    text = (
        "diff --git a/sp ace.py b/sp ace.py\n"
        "--- a/sp ace.py\t\n"
        "+++ b/sp ace.py\t\n"
        "@@ -2 +2 @@ a=1\n"
        "-b=2\n"
        "+b=22\n"
        "@@ -3,0 +4 @@ c=3\n"
        "+d=4\n"
    )
    changed, _ = parse_diff_text(text)
    assert changed == {"sp ace.py": [[2, 2], [4, 4]]}


def test_quoted_unicode_path_and_no_misattribution():
    text = (
        "diff --git a/sp ace.py b/sp ace.py\n"
        "--- a/sp ace.py\t\n"
        "+++ b/sp ace.py\t\n"
        "@@ -2 +2 @@ a=1\n"
        "+b=22\n"
        'diff --git "a/uni-\\303\\244.py" "b/uni-\\303\\244.py"\n'
        '--- "a/uni-\\303\\244.py"\n'
        '+++ "b/uni-\\303\\244.py"\n'
        "@@ -1,0 +2 @@ z=1\n"
        "+w=2\n"
    )
    changed, _ = parse_diff_text(text)
    assert changed == {"sp ace.py": [[2, 2]], "uni-ä.py": [[2, 2]]}


def test_deleted_file_contributes_no_ranges():
    text = (
        "diff --git a/gone.py b/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-x=1\n"
    )
    changed, digest = parse_diff_text(text)
    assert changed == {}
    assert digest != diffs.sha_short("")


def test_new_file_and_rename():
    text = (
        "diff --git a/new.py b/new.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+a=1\n"
        "diff --git a/old.py b/renamed.py\n"
        "similarity index 90%\n"
        "--- a/old.py\n"
        "+++ b/renamed.py\n"
        "@@ -5,3 +5,4 @@\n"
        "+extra=1\n"
    )
    changed, _ = parse_diff_text(text)
    assert changed == {"new.py": [[1, 2]], "renamed.py": [[5, 8]]}


def test_binary_and_empty_diffs():
    binary = (
        "diff --git a/logo.png b/logo.png\n"
        "Binary files a/logo.png and b/logo.png differ\n"
    )
    changed, _ = parse_diff_text(binary)
    assert changed == {}
    changed, digest = parse_diff_text("")
    assert changed == {}
    assert digest == diffs.sha_short("")


def test_omitted_counts_and_hunk_trailers():
    text = (
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -2 +2 @@ def f(x+1):\n"
        "+y\n"
    )
    changed, _ = parse_diff_text(text)
    assert changed == {"a.py": [[2, 2]]}


def test_git_failure_raises_clear_error(tmp_path, monkeypatch):
    class Boom:
        returncode = 1
        stdout = ""
        stderr = "fatal: not a git repository"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Boom())
    with pytest.raises(GitError, match="git diff failed"):
        diffs.changed_lines(tmp_path)


def test_missing_git_binary_raises_clear_error(tmp_path, monkeypatch):
    def _missing(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _missing)
    with pytest.raises(GitError, match="git is not available"):
        diffs.changed_lines(tmp_path)


def test_require_git_repo_rejects_non_repo(tmp_path):
    with pytest.raises(GitError, match="not inside a git repository"):
        diffs.require_git_repo(tmp_path)
