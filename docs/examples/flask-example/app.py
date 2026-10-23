"""
app.py - a Flask service that serves the model and watches its live inputs.

    python app.py            # starts on http://127.0.0.1:5000

    POST /predict   {"age": 35, "income_k": 52, "credit_score": 650}
    GET  /health    the guard's status (rows seen, drift, health score)

Set PSIWATCH_WEBHOOK to a Slack / Discord / generic webhook URL to get a
message when the data drifts. Without it, the alert is printed in this
terminal.
"""
import logging
import os

import joblib
import psiwatch
from flask import Flask, jsonify, request

# psiwatch reports drift through Python logging, which is silent until you
# configure it. Without this line you would see no alert in the terminal.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model.joblib")

model = joblib.load(MODEL_PATH)

# Loads model.joblib.psiwatch.json. Warns if the model file changed since the
# baseline was saved (i.e. you retrained but forgot to re-save the baseline).
guard = psiwatch.Guard.from_model(
    MODEL_PATH,
    window=200,            # compare the last 200 requests...
    min_samples=100,       # ...once at least 100 have arrived
    check_every=50,        # ...and re-check every 50 requests
    webhook=os.environ.get("PSIWATCH_WEBHOOK"),
)


@guard.watch                        # records the input; can never break a prediction
def score(features):
    row = [features["age"], features["income_k"], features["credit_score"]]
    return float(model.predict_proba([row])[0][1])


app = Flask(__name__)


@app.post("/predict")
def predict():
    return jsonify(approval_probability=round(score(request.get_json()), 4))


@app.get("/health")
def health():
    return jsonify(guard.status())


if __name__ == "__main__":
    app.run(port=5000)
