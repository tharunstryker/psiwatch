"""
test_v0_12_0_fixes.py — Manual verification script for the three v0.12.0 fixes.

Run in Termux:
    cd psiwatch
    python test_v0_12_0_fixes.py

No pytest needed — plain script, prints PASS/FAIL per check.
"""

import os
import sys
import json
import socket
import subprocess

sys.path.insert(0, "src")
import os as _os
_os.makedirs("tmp_test_files", exist_ok=True)

results = []

def check(label, condition):
    status = "PASS" if condition else "FAIL"
    results.append(condition)
    print(f"  [{status}] {label}")


print("\n=== 1. Lock file fingerprint size (not raw values) ===\n")

from psiwatch.locker import save_lock, load_lock, lock_info

big_baseline = {"age": list(range(20000))}
save_lock(big_baseline, lock_path="./tmp_test_files/big.lock.json")

size = os.path.getsize("./tmp_test_files/big.lock.json")
data = json.load(open("./tmp_test_files/big.lock.json"))

check(f"Lock file for 20,000 rows is small (got {size} bytes)", size < 5000)
check("No raw 'values_sample' key in lock file", "values_sample" not in data["columns"]["age"])
check("Lock contains a histogram fingerprint instead", "hist_counts" in data["columns"]["age"]["summary"])


print("\n=== 2. Drift detection still works through a lock file ===\n")

baseline = {"age": [22, 23, 21, 24, 25] * 20}
stable_new = {"age": [22, 23, 21, 24, 25] * 20}
drifted_new = {"age": [40, 42, 44, 46, 48] * 20}

save_lock(baseline, lock_path="./tmp_test_files/test.lock.json")
r_stable = load_lock(stable_new, lock_path="./tmp_test_files/test.lock.json")
r_drift = load_lock(drifted_new, lock_path="./tmp_test_files/test.lock.json")

check("Stable data passes (health_score == 100)", r_stable["health_score"] == 100)
check("Drifted data flagged HIGH", r_drift["columns"]["age"]["severity"] == "HIGH")


print("\n=== 3. Old-format lock files are rejected, not silently misread ===\n")

legacy_lock = {
    "psiwatch_lock": True,
    "version": "1",
    "created_at": "2026-01-01 00:00:00",
    "source": "old.csv",
    "columns": {"age": {"type": "numeric", "count": 3, "values_sample": [1.0, 2.0, 3.0]}},
}
json.dump(legacy_lock, open("./tmp_test_files/legacy.lock.json", "w"))

try:
    load_lock({"age": [1, 2, 3]}, lock_path="./tmp_test_files/legacy.lock.json")
    check("Legacy v1 lock file raises an error", False)
except ValueError as e:
    check("Legacy v1 lock file raises an error", True)
    print(f"         → {e}")


print("\n=== 4. HTML report escapes malicious column/category names ===\n")

from psiwatch import compare

baseline_xss = {"<script>alert(1)</script>": [1, 2, 3, 4, 5] * 5,
                "city": ["Chennai", "Delhi"] * 5}
new_xss = {"<script>alert(1)</script>": [50, 60, 70, 80, 90] * 5,
           "city": ["Chennai", "<img src=x onerror=alert(2)>"] * 5}

compare(baseline_xss, new_xss, output="./tmp_test_files/xss_test.html")
html_content = open("./tmp_test_files/xss_test.html").read()

check("Raw <script> tag NOT present in HTML", "<script>alert(1)</script>" not in html_content)
check("Raw <img onerror> NOT present in HTML", "<img src=x onerror=alert(2)>" not in html_content)
check("Escaped version IS present", "&lt;script&gt;" in html_content)


print("\n=== 5. import psiwatch makes zero network calls ===\n")

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
env = {**os.environ, "PYTHONPATH": "src"}
result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
check("import psiwatch triggers 0 network calls", result.stdout.strip() == "0")


print("\n" + "=" * 50)
passed = sum(results)
total = len(results)
print(f"  {passed}/{total} checks passed")
print("=" * 50 + "\n")

sys.exit(0 if passed == total else 1)
