# joblib + Flask + psiwatch

A loan-approval model served by Flask. psiwatch warns you when the requests
it receives stop looking like the data the model was trained on.

```
train.py          train a model, save it, save a psiwatch baseline next to it
app.py            Flask service: POST /predict, GET /health, guarded by psiwatch
send_traffic.py   send fake healthy or drifted requests (standard library only)
simple_model.py   stand-in model, used only if scikit-learn is not installed
```

## Run it

```bash
pip install flask joblib scikit-learn psiwatch   # scikit-learn is optional here
python train.py          # creates model.joblib and model.joblib.psiwatch.json
python app.py            # leave this running
```

In a second terminal (in Termux: swipe from the left edge, **New session**):

```bash
python send_traffic.py healthy    # looks like the training data -> "alerts": 0
python send_traffic.py drifted    # older, richer people         -> "alerts": 1
```

Expected, in the `app.py` terminal:

```
WARNING psiwatch: drift detected in model.joblib - health 17/100, drifted: age, credit_score, income_k
```

`curl http://127.0.0.1:5000/health` shows the guard's status at any time.

## The part that matters (`app.py`)

```python
guard = psiwatch.Guard.from_model("model.joblib", webhook=SLACK_URL)

@guard.watch
def score(features):
    ...
```

- `save_baseline()` (in `train.py`) stores summary statistics only, never raw rows.
- `@guard.watch` records each request's input. Checks run in a background
  thread and can never break a prediction.
- The guard compares the last 200 requests with the baseline, re-checking
  every 50. Set `PSIWATCH_WEBHOOK` to get Slack / Discord / webhook alerts.
- Retrain and forget to re-save the baseline? `Guard.from_model` warns that
  the baseline belongs to a different model file.

## Limits

- It watches inputs, not accuracy.
- Flask's built-in server is for development. Under gunicorn with several
  workers, each worker keeps its own window and alerts once.
- `app.py` calls `logging.basicConfig(...)`. psiwatch reports through Python
  logging, so without that line the alert is silent.
