"""
send_traffic.py - send fake requests to the running service (standard library only).

    python send_traffic.py healthy       # 200 requests that look like the training data
    python send_traffic.py drifted       # 200 requests from a different population
    python send_traffic.py drifted 400   # choose how many
"""
import json
import random
import sys
import time
import urllib.request

URL = "http://127.0.0.1:5000"
mode = sys.argv[1] if len(sys.argv) > 1 else "healthy"
count = int(sys.argv[2]) if len(sys.argv) > 2 else 200
if mode not in ("healthy", "drifted"):
    sys.exit("usage: python send_traffic.py healthy|drifted [count]")

rng = random.Random()
for _ in range(count):
    if mode == "healthy":      # same as the training data
        row = {"age": rng.gauss(35, 6), "income_k": rng.gauss(52, 8),
               "credit_score": rng.gauss(650, 40)}
    else:                      # older, richer, lower credit scores
        row = {"age": rng.gauss(52, 6), "income_k": rng.gauss(80, 8),
               "credit_score": rng.gauss(590, 40)}
    req = urllib.request.Request(
        URL + "/predict", data=json.dumps(row).encode(),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req).read()

time.sleep(1)    # the drift check runs in a background thread
with urllib.request.urlopen(URL + "/health") as r:
    status = json.load(r)
print(f"sent {count} {mode} requests")
print(json.dumps(status, indent=2))
