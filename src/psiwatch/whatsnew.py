"""
whatsnew.py — release highlights shown by `psiwatch version`.

NOTES holds short highlights for recent releases so they ship inside the
installed package (CHANGELOG.md is not installed by pip). The full history
lives in CHANGELOG.md. When you cut a release, add its entry to BOTH — a
test fails if the current version is missing from either.
"""

CHANGELOG_URL = "https://github.com/tharunstryker/psiwatch/blob/main/CHANGELOG.md"

NOTES = {
    "0.15.1": {
        "title": "See what's new from the CLI",
        "items": [
            "psiwatch version now shows the highlights of your installed release "
            "and a link to the full changelog.",
            "psiwatch version --short prints only the version number (for scripts).",
            "README restructured; full release history moved to CHANGELOG.md.",
        ],
    },
    "0.15.0": {
        "title": "Free-text column drift",
        "items": [
            "Text columns (chat messages, reviews, tickets) are auto-detected and analysed: "
            "vocabulary drift, rising/falling/new words, unseen-word rate, script/language mix, "
            "length and structure.",
            "Pure Python, zero dependencies, no models. Tamil/Hindi/CJK tokenised correctly.",
            "New flags: --text-columns a,b  and  --no-text-detect (config: text_columns, detect_text).",
            "A text column that used to show as [categorical] now shows as [text].",
        ],
    },
    "0.14.0": {
        "title": "Drift charts",
        "items": [
            "--plot drift.png draws baseline-vs-new charts (pip install psiwatch[charts]).",
            "--embed-chart puts the chart inside the HTML report.",
        ],
    },
}


def format_whatsnew(version):
    """Return the 'what's new' text for `version` (always ends with the changelog link)."""
    entry = NOTES.get(version)
    lines = []
    if entry:
        lines.append(f"What's new in {version} — {entry['title']}")
        lines.extend(f"  • {item}" for item in entry["items"])
        lines.append("")
    lines.append(f"Full changelog: {CHANGELOG_URL}")
    return "\n".join(lines)
