"""
test_changelog.py — `psiwatch version` shows what's new, and release notes
can't be forgotten: the current version must appear in whatsnew.py AND
CHANGELOG.md.
"""

import os
import sys

import pytest

from psiwatch import __version__, cli
from psiwatch.whatsnew import CHANGELOG_URL, NOTES, format_whatsnew


def _run(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["psiwatch", *args])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    return capsys.readouterr().out


def test_current_version_has_release_notes():
    assert __version__ in NOTES, (
        f"Add a {__version__} entry to src/psiwatch/whatsnew.py (and CHANGELOG.md)"
    )
    assert NOTES[__version__]["items"]


def test_format_whatsnew_contains_title_items_and_link():
    out = format_whatsnew(__version__)
    assert f"What's new in {__version__}" in out
    assert NOTES[__version__]["items"][0] in out
    assert CHANGELOG_URL in out


def test_unknown_version_still_shows_changelog_link():
    assert format_whatsnew("0.0.0-dev").strip() == f"Full changelog: {CHANGELOG_URL}"


def test_version_command_shows_whats_new(monkeypatch, capsys):
    out = _run(monkeypatch, capsys, "version")
    assert out.splitlines()[0] == f"psiwatch {__version__}"
    assert "What's new" in out and CHANGELOG_URL in out


def test_version_short_prints_only_the_number(monkeypatch, capsys):
    out = _run(monkeypatch, capsys, "version", "--short")
    assert out.strip() == f"psiwatch {__version__}"


def test_changelog_md_has_current_version_first():
    path = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")
    if not os.path.exists(path):
        pytest.skip("CHANGELOG.md not present (running outside the repo)")
    with open(path, encoding="utf-8") as f:
        headings = [line for line in f if line.startswith("## v")]
    assert headings, "CHANGELOG.md has no '## vX.Y.Z' entries"
    assert headings[0].startswith(f"## v{__version__}"), (
        f"Newest CHANGELOG.md entry is {headings[0].strip()!r}, expected v{__version__}"
    )
