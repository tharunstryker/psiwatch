"""
test_updater.py — Update-check banner behavior.

Regression test for the v0.12.0 fix: `import psiwatch` previously made
an unconditional network call to PyPI on every import, including inside
library code (training pipelines, notebooks, CI steps) that never
touches the CLI. The check now only fires from the `psiwatch` CLI
entry point.
"""

import os
import subprocess
import sys


def test_import_psiwatch_makes_no_network_call():
    # Run in a clean subprocess so we observe true import-time behavior,
    # not state from a module that's already been imported elsewhere in
    # the test session. Explicitly set PYTHONPATH to src/ since pytest's
    # own `pythonpath` config option only affects pytest's collector
    # process, not subprocesses spawned from within a test.
    code = (
        "import socket\n"
        "calls = []\n"
        "def fake(self, *a, **k):\n"
        "    calls.append(a)\n"
        "    raise socket.timeout('blocked')\n"
        "socket.socket.connect = fake\n"
        "import psiwatch\n"
        "print(len(calls))\n"
    )
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            timeout=15, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0", (
        "import psiwatch made a network call — the update-check banner "
        "must only run from the CLI entry point, not on plain import."
    )
