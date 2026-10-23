"""
train.py - train a loan-approval model, save it, and save a psiwatch baseline
next to it.

    python train.py

Creates:  model.joblib                  the model
          model.joblib.psiwatch.json    summary statistics of the training data
                                        (no raw rows) + the model file's hash
"""
import os
import random

import joblib
import psiwatch

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model.joblib")

# --- 1. Make some training data (stand-in for your real dataset) ------------
rng = random.Random(0)
N = 2000
data = {
    "age":          [round(rng.gauss(35, 6)) for _ in range(N)],
    "income_k":     [round(rng.gauss(52, 8), 1) for _ in range(N)],   # thousands
    "credit_score": [round(rng.gauss(650, 40)) for _ in range(N)],
}
X = [list(row) for row in zip(data["age"], data["income_k"], data["credit_score"])]
y = [int(0.12 * (a - 35) + 0.06 * (i - 52) + 0.02 * (c - 650) + rng.gauss(0, 1) > 0)
     for a, i, c in X]

# --- 2. Train ----------------------------------------------------------------
try:
    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression(max_iter=1000).fit(X, y)
    print("Trained a scikit-learn LogisticRegression.")
except ImportError:
    from simple_model import SimpleModel
    model = SimpleModel().fit(X, y)
    print("scikit-learn not installed - using the built-in SimpleModel instead.")

# --- 3. Save the model, then the data fingerprint next to it ----------------
joblib.dump(model, MODEL_PATH)
psiwatch.save_baseline(data, MODEL_PATH)        # -> model.joblib.psiwatch.json
print(f"Saved {os.path.basename(MODEL_PATH)} and {os.path.basename(MODEL_PATH)}.psiwatch.json")
