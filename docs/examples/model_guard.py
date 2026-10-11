"""
model_guard.py — psiwatch Guard demo. Standard library only (no scikit-learn,
Flask or joblib needed): a toy model saved with pickle.

    python model_guard.py

Shows the whole loop:
  1. train + save a model
  2. save a data baseline next to it            (psiwatch.save_baseline)
  3. serve predictions through a guard          (@guard.watch)
  4. real traffic drifts -> psiwatch alerts you
"""
import os
import pickle
import random
import tempfile

import psiwatch


class ToyModel:
    """Approves people whose age * 1000 + income is high enough."""
    def predict(self, age, income):
        return int(age * 1000 + income > 87000)


workdir = tempfile.mkdtemp()
model_path = os.path.join(workdir, "model.pkl")
rng = random.Random(0)

# 1 + 2. "Train", save the model, and save the training data's fingerprint beside it.
train = {
    "age": [round(rng.gauss(35, 6)) for _ in range(2000)],
    "income": [round(rng.gauss(52000, 8000)) for _ in range(2000)],
}
with open(model_path, "wb") as f:
    pickle.dump(ToyModel(), f)
psiwatch.save_baseline(train, model_path)          # -> model.pkl.psiwatch.json

# 3. In the service: load the model and its guard together.
with open(model_path, "rb") as f:
    model = pickle.load(f)

alerts = []
guard = psiwatch.Guard.from_model(
    model_path,
    window=300,
    check_every=100,
    on_drift=alerts.append,        # or: webhook="https://hooks.slack.com/services/..."
    background=False,              # inline so this demo prints in order
)


@guard.watch
def predict(features):
    return model.predict(features["age"], features["income"])


# 4. Healthy traffic, then users get older and richer.
for _ in range(300):
    predict({"age": rng.gauss(35, 6), "income": rng.gauss(52000, 8000)})
print(f"\nhealthy traffic  -> alerts: {len(alerts)}")

for _ in range(300):
    predict({"age": rng.gauss(52, 6), "income": rng.gauss(80000, 8000)})
print(f"drifted traffic  -> alerts: {len(alerts)}")
print(f"drifted columns  -> {alerts[0]['summary']['drifted_columns']}")
print(f"guard status     -> {guard.status()}")
