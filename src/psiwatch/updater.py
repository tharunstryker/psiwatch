"""
updater.py — Version check + self-update for psiwatch.

- Auto-checks PyPI on every run (24h cached, never blocks)
- `psiwatch update` command runs pip upgrade directly from terminal
"""

import json
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error

PYPI_URL = "https://pypi.org/pypi/psiwatch/json"
CACHE_FILE = os.path.join(os.path.expanduser("~"), ".psiwatch_version_cache")
CACHE_TTL = 86400  # 24 hours


def _get_latest_from_pypi():
    try:
        req = urllib.request.Request(
            PYPI_URL,
            headers={"User-Agent": "psiwatch-version-check"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data["info"]["version"]
    except Exception:
        return None


def _read_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            return data.get("latest"), data.get("ts", 0)
    except Exception:
        return None, 0


def _write_cache(latest_version):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"latest": latest_version, "ts": time.time()}, f)
    except Exception:
        pass


def _parse_version(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0, 0, 0)


def check_for_update(current_version, silent=False):
    """
    Check PyPI for newer version. 24h cached.
    Returns (latest_version, update_available).
    """
    cached_latest, ts = _read_cache()
    now = time.time()

    if cached_latest and (now - ts) < CACHE_TTL:
        latest = cached_latest
    else:
        latest = _get_latest_from_pypi()
        if latest:
            _write_cache(latest)

    if not latest:
        return None, False

    update_available = _parse_version(latest) > _parse_version(current_version)

    if update_available and not silent:
        print(
            f"\n  ╔══════════════════════════════════════════════════════╗\n"
            f"  ║  psiwatch update available: {current_version} → {latest:<8}            ║\n"
            f"  ║  Run: psiwatch update  (or pip install -U psiwatch)  ║\n"
            f"  ╚══════════════════════════════════════════════════════╝\n"
        )

    return latest, update_available


def run_self_update():
    """
    Run `pip install --upgrade psiwatch` from within the CLI.
    Shows live pip output. Returns True on success.
    """
    print("\n  Checking for latest version...")
    latest = _get_latest_from_pypi()
    if not latest:
        print("  Could not reach PyPI. Check your internet connection.")
        return False

    from . import __version__
    if _parse_version(latest) <= _parse_version(__version__):
        print(f"  Already up to date — psiwatch {__version__}")
        return True

    print(f"  Updating psiwatch {__version__} → {latest}...\n")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "psiwatch"],
        text=True
    )

    if result.returncode == 0:
        # Bust the cache so next run shows correct version
        _write_cache(latest)
        print(f"\n  psiwatch updated to {latest}. Restart your terminal to use it.")
        return True
    else:
        print("\n  Update failed. Try manually: pip install --upgrade psiwatch")
        return False
