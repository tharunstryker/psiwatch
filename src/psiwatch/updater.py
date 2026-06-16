"""
updater.py — Version check + self-update for psiwatch.

- On every run: silently checks PyPI for a newer version (cached 24h).
- Shows a clean banner if an update is available.
- `psiwatch update` command: runs pip install --upgrade psiwatch in-process.
- Silent in CI (PSIWATCH_SILENT=1 or CI=true env vars).
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


def _is_ci():
    """Detect CI/CD environment — suppress banners there."""
    return (
        os.environ.get("CI", "").lower() in ("true", "1", "yes")
        or os.environ.get("PSIWATCH_SILENT", "").lower() in ("true", "1", "yes")
        or os.environ.get("GITHUB_ACTIONS", "") == "true"
    )


def _get_latest_from_pypi():
    """Fetch latest version string from PyPI. Returns None on any error."""
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


def _banner(current, latest):
    """Render a fixed-width update banner. Always 52 chars wide inside the box."""
    line = f"  psiwatch update available: {current} → {latest}"
    pad = 52 - len(line)
    cmd_line = "  Run: pip install --upgrade psiwatch"
    cmd_pad = 52 - len(cmd_line)
    print(
        f"\n  ╔{'═' * 52}╗\n"
        f"  ║{line}{' ' * pad}║\n"
        f"  ║{cmd_line}{' ' * cmd_pad}║\n"
        f"  ╚{'═' * 52}╝\n"
    )


def check_for_update(current_version, silent=False):
    """
    Check PyPI for a newer version. Uses 24h disk cache.

    Args:
        current_version: str — e.g. "0.10.0"
        silent: suppress banner even if update available

    Returns:
        (latest: str | None, update_available: bool)
    """
    if silent or _is_ci():
        return None, False

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

    if update_available:
        _banner(current_version, latest)

    return latest, update_available


def do_upgrade():
    """
    Run `pip install --upgrade psiwatch` in a subprocess.
    Called by `psiwatch update` CLI command.
    Returns exit code.
    """
    print("  Upgrading psiwatch...\n")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "psiwatch"],
        check=False
    )
    if result.returncode == 0:
        print("\n  psiwatch upgraded successfully.")
        print("  Run `psiwatch version` to confirm.")
    else:
        print("\n  Upgrade failed. Try manually:")
        print("  pip install --upgrade psiwatch")
    return result.returncode
