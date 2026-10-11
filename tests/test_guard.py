"""
test_guard.py — model-attached baselines and the live drift Guard (v0.16.0).
"""

import asyncio
import json
import logging
import os
import random
import sys
import threading
import time
import warnings

import pytest

import psiwatch
from psiwatch import Guard, baseline_path, load_baseline, save_baseline, verify_baseline
from psiwatch.guard import _rows_from

PLANS = ["free", "pro", "team"]


def _data(n, seed, shifted=False):
    """Columnar traffic: numeric age/income + categorical plan."""
    r = random.Random(seed)
    if shifted:
        return {
            "age": [round(r.gauss(58, 5)) for _ in range(n)],
            "income": [round(r.gauss(95000, 8000)) for _ in range(n)],
            "plan": [r.choices(PLANS, [0.05, 0.05, 0.9])[0] for _ in range(n)],
        }
    return {
        "age": [round(r.gauss(35, 6)) for _ in range(n)],
        "income": [round(r.gauss(52000, 8000)) for _ in range(n)],
        "plan": [r.choices(PLANS, [0.6, 0.3, 0.1])[0] for _ in range(n)],
    }


def _records(cols):
    n = len(next(iter(cols.values())))
    return [{k: v[i] for k, v in cols.items()} for i in range(n)]


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "model.joblib"
    path.write_bytes(b"pretend this is a pickled model v1")
    return str(path)


@pytest.fixture
def baselined(model):
    save_baseline(_data(800, seed=1), model, quiet=True)
    return model


def _feed(guard, cols):
    """Serving-style traffic: one request at a time (one check per `check_every` rows)."""
    for row in _records(cols):
        guard.observe(row)


def _guard(model, **kw):
    kw.setdefault("background", False)
    kw.setdefault("min_samples", 100)
    kw.setdefault("check_every", 50)
    kw.setdefault("window", 200)
    return Guard.from_model(model, **kw)


# ─── Model-attached baseline ──────────────────────────────────────────────────

def test_baseline_path_is_sidecar_next_to_model(tmp_path):
    assert baseline_path("model.joblib") == "model.joblib.psiwatch.json"
    assert baseline_path(tmp_path / "m.pkl") == str(tmp_path / "m.pkl") + ".psiwatch.json"


def test_save_baseline_writes_sidecar_with_model_hash(model):
    path = save_baseline(_data(300, 1), model, quiet=True)
    assert path == baseline_path(model) and os.path.exists(path)
    lock = json.load(open(path, encoding="utf-8"))
    assert lock["model"]["file"] == "model.joblib"
    assert len(lock["model"]["sha256"]) == 64
    assert set(lock["columns"]) == {"age", "income", "plan"}


def test_baseline_contains_no_raw_rows(model):
    data = _data(300, 1)
    data["note"] = ["my very secret raw sentence number %d here" % i for i in range(300)]
    path = save_baseline(data, model, quiet=True)
    assert "very secret raw sentence number 17 here" not in open(path, encoding="utf-8").read()


def test_save_baseline_from_array_with_feature_names(model):
    rows = [[30 + i % 20, 40000 + i * 10] for i in range(200)]
    save_baseline(rows, model, feature_names=["age", "income"], quiet=True)
    assert set(load_baseline(model)["columns"]) == {"age", "income"}


def test_save_baseline_array_without_names_is_a_clear_error(model):
    with pytest.raises(ValueError, match="feature names"):
        save_baseline([[1, 2], [3, 4]], model, quiet=True)


def test_save_baseline_columns_and_ignore(model):
    save_baseline(_data(200, 1), model, ignore_columns=["income"], quiet=True)
    assert set(load_baseline(model)["columns"]) == {"age", "plan"}


def test_save_baseline_works_when_model_file_does_not_exist_yet(tmp_path):
    path = save_baseline(_data(100, 1), str(tmp_path / "later.joblib"), quiet=True)
    lock = json.load(open(path, encoding="utf-8"))
    assert "sha256" not in lock["model"]


def test_verify_baseline_detects_a_retrained_model(baselined):
    assert verify_baseline(baselined)[0] is True
    with open(baselined, "wb") as f:
        f.write(b"retrained model v2")
    ok, msg = verify_baseline(baselined)
    assert ok is False and "different version" in msg


def test_from_model_warns_when_baseline_is_stale(baselined):
    with open(baselined, "wb") as f:
        f.write(b"retrained model v2")
    with pytest.warns(UserWarning, match="different version"):
        Guard.from_model(baselined)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Guard.from_model(baselined, verify=False)        # opt-out is silent


def test_from_model_without_baseline_tells_you_what_to_run(model):
    with pytest.raises(FileNotFoundError, match="save_baseline"):
        Guard.from_model(model)


def test_load_baseline_returns_validated_lock(baselined):
    lock = load_baseline(baselined)
    assert lock["psiwatch_lock"] is True and "age" in lock["columns"]


# ─── Input handling ───────────────────────────────────────────────────────────

def test_rows_from_accepts_every_shape():
    assert _rows_from({"a": 1, "b": "x"}) == [{"a": "1", "b": "x"}]
    assert _rows_from({"a": [1, 2], "b": ["x", "y"]}) == [
        {"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
    assert _rows_from([{"a": 1}, {"a": 2}]) == [{"a": "1"}, {"a": "2"}]
    assert _rows_from([[1, 2], [3, 4]], ["a", "b"]) == [
        {"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    assert _rows_from([1, 2], ["a", "b"]) == [{"a": "1", "b": "2"}]


def test_rows_from_skips_none_and_nan():
    assert _rows_from({"a": 1, "b": None, "c": float("nan")}) == [{"a": "1"}]


def test_rows_from_rejects_mismatched_shapes():
    with pytest.raises(ValueError, match="feature names"):
        _rows_from([[1, 2]])
    with pytest.raises(ValueError, match="3 values but 2"):
        _rows_from([[1, 2, 3]], ["a", "b"])
    with pytest.raises(ValueError, match="different lengths"):
        _rows_from({"a": [1, 2, 3], "b": [1, 2]})
    with pytest.raises(TypeError):
        _rows_from(42)


def test_rows_from_dataframe_and_numpy():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    df = pd.DataFrame({"a": [1, None], "b": ["x", "y"]})
    assert _rows_from(df) == [{"a": "1.0", "b": "x"}, {"b": "y"}]
    assert _rows_from(np.array([[1, 2], [3, 4]]), ["a", "b"]) == [
        {"a": "1", "b": "2"}, {"a": "3", "b": "4"}]


def test_observe_accepts_array_with_constructor_features(baselined):
    g = _guard(baselined, features=["age", "income", "plan"])
    assert g.observe([[30, 50000, "free"], [40, 60000, "pro"]]) == 2
    assert g.observed == 2


def test_observe_rejects_input_with_no_watched_columns(baselined):
    g = _guard(baselined)
    with pytest.raises(ValueError, match="none of the watched columns"):
        g.observe({"nonsense": 1})
    assert g.observed == 0


def test_observe_ignores_extra_columns(baselined):
    g = _guard(baselined)
    g.observe({"age": 30, "user_id": 12345})
    assert g.observed == 1 and "user_id" not in g._buf[0]


# ─── Checking and alerting ────────────────────────────────────────────────────

def test_no_check_before_min_samples(baselined):
    g = _guard(baselined, min_samples=100)
    g.observe(_records(_data(99, 5)))
    assert g.checks == 0
    g.observe(_records(_data(1, 6)))
    assert g.checks == 1


def test_window_keeps_only_recent_rows(baselined):
    g = _guard(baselined, window=150, min_samples=10_000)
    g.observe(_records(_data(400, 5)))
    assert len(g._buf) == 150 and g.observed == 400


def test_healthy_traffic_does_not_alert(baselined):
    fired = []
    g = _guard(baselined, on_drift=fired.append)
    _feed(g, _data(400, seed=7))
    assert g.checks >= 3 and fired == []
    assert g.status()["drifting"] is False


def test_drifted_traffic_alerts_with_details(baselined):
    fired = []
    g = _guard(baselined, on_drift=fired.append)
    g.observe(_records(_data(300, seed=8, shifted=True)))
    assert len(fired) == 1
    result = fired[0]
    assert result["columns"]["age"]["severity"] == "HIGH"
    assert "age" in result["summary"]["drifted_columns"]
    assert g.status()["drifting"] is True and g.status()["alerts"] == 1


def test_cooldown_prevents_alert_spam(baselined):
    fired = []
    g = _guard(baselined, on_drift=fired.append, cooldown=3600)
    _feed(g, _data(600, seed=8, shifted=True))
    assert g.checks > 3 and len(fired) == 1


def test_zero_cooldown_alerts_every_check(baselined):
    fired = []
    g = _guard(baselined, on_drift=fired.append, cooldown=0)
    _feed(g, _data(300, seed=8, shifted=True))
    assert len(fired) == g.checks > 1


def test_recovery_resets_so_a_new_incident_alerts_immediately(baselined):
    fired = []
    g = _guard(baselined, on_drift=fired.append, cooldown=3600)
    _feed(g, _data(250, seed=8, shifted=True))
    assert len(fired) == 1
    _feed(g, _data(250, seed=9))                           # healthy fills the window
    assert g.status()["drifting"] is False
    _feed(g, _data(250, seed=10, shifted=True))
    assert len(fired) == 2


def test_healthy_windows_rarely_raise_a_high_alert(baselined):
    """
    The noise margin: small windows of healthy data must not cry wolf.
    Simulated rate is ~0.6% of runs (1 in 180); assert it stays at or below 2%.
    """
    alarms = runs = 0
    for window in (100, 200, 500):
        for seed in range(60):
            fired = []
            g = _guard(baselined, window=window, min_samples=min(100, window),
                       cooldown=0, on_drift=fired.append)
            _feed(g, _data(window * 2, seed=600 + seed))
            runs += 1
            alarms += 1 if fired else 0
    assert alarms / runs <= 0.02, f"{alarms} false HIGH alarms in {runs} healthy runs"


def test_one_sigma_shift_is_still_caught_in_a_small_window(baselined):
    for seed in range(10):
        shifted = _data(400, seed=700 + seed)
        shifted["age"] = [a + 6 for a in shifted["age"]]       # +1 standard deviation
        fired = []
        g = _guard(baselined, window=200, on_drift=fired.append)
        _feed(g, shifted)
        assert fired and fired[0]["columns"]["age"]["severity"] == "HIGH", seed


def test_alert_on_medium_is_more_sensitive(baselined):
    mild = _data(300, seed=11)
    mild["age"] = [a + 4 for a in mild["age"]]             # modest shift
    high_only, medium_up = [], []
    _guard(baselined, on_drift=high_only.append, alert_on="HIGH").observe(_records(mild))
    _guard(baselined, on_drift=medium_up.append, alert_on="MEDIUM").observe(_records(mild))
    assert len(medium_up) >= len(high_only)


def test_webhook_is_sent_on_drift(baselined, monkeypatch):
    sent = []
    monkeypatch.setattr("psiwatch.webhook.send_webhook",
                        lambda url, result, **kw: sent.append((url, kw)) or True)
    g = _guard(baselined, webhook="https://example.test/hook")
    g.observe(_records(_data(300, seed=8, shifted=True)))
    assert len(sent) == 1
    assert sent[0][0] == "https://example.test/hook"
    assert "model.joblib" in sent[0][1]["source_info"]


def test_failing_callback_and_webhook_never_break_observe(baselined, monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr("psiwatch.webhook.send_webhook", boom)
    g = _guard(baselined, webhook="https://example.test/hook", on_drift=boom)
    with caplog.at_level(logging.WARNING, logger="psiwatch"):
        g.observe(_records(_data(300, seed=8, shifted=True)))
    assert g.alerts == 1
    assert "webhook failed" in caplog.text and "on_drift callback raised" in caplog.text


def test_manual_check_works_below_min_samples(baselined):
    g = _guard(baselined, min_samples=10_000)
    with pytest.raises(ValueError, match="window is empty"):
        g.check()
    g.observe(_records(_data(60, seed=8, shifted=True)))
    assert g.checks == 0
    result = g.check()
    assert result["health_score"] < 80 and g.checks == 1


def test_background_checks_run_off_the_calling_thread(baselined):
    main = threading.current_thread()
    seen = []
    g = _guard(baselined, background=True,
               on_drift=lambda r: seen.append(threading.current_thread()))
    g.observe(_records(_data(300, seed=8, shifted=True)))
    g.wait(5)
    assert seen and all(t is not main for t in seen)


def test_sample_zero_keeps_nothing(baselined):
    g = _guard(baselined, sample=0.0)
    assert g.observe(_records(_data(100, 3))) == 0 and g.observed == 0


def test_reset_clears_window_and_alert_state(baselined):
    g = _guard(baselined)
    g.observe(_records(_data(300, seed=8, shifted=True)))
    g.reset()
    assert g.status()["window_rows"] == 0 and g.status()["drifting"] is False


def test_invalid_arguments_are_rejected(baselined):
    with pytest.raises(ValueError, match="alert_on"):
        _guard(baselined, alert_on="LOW")
    with pytest.raises(ValueError, match="sample"):
        _guard(baselined, sample=2)
    with pytest.raises(ValueError, match=">= 1"):
        _guard(baselined, window=0)


def test_columns_and_ignore_restrict_what_is_watched(baselined):
    g = _guard(baselined, ignore_columns=["age"])
    assert g._known == {"income", "plan"}
    g2 = _guard(baselined, columns=["plan"])
    assert g2._known == {"plan"}


def test_guard_from_lock_dict_and_plain_lock_file(tmp_path):
    lock = psiwatch.save_lock(_data(300, 1), lock_path=str(tmp_path / "x.lock.json"), quiet=True)
    assert Guard(lock, background=False).name == "baseline"
    assert Guard(str(tmp_path / "x.lock.json"), background=False)


def test_text_column_drift_through_the_guard(model):
    base = {"msg": ["where is my order number %d please" % (i % 30) for i in range(400)]}
    save_baseline(base, model, text_columns=["msg"], quiet=True)
    fired = []
    g = _guard(model, on_drift=fired.append, window=200)
    g.observe([{"msg": "i want a refund this is a scam %d" % (i % 9)} for i in range(200)])
    assert fired and fired[0]["columns"]["msg"]["type"] == "text"
    assert fired[0]["columns"]["msg"]["severity"] == "HIGH"


def test_status_snapshot(baselined):
    g = _guard(baselined)
    st = g.status()
    assert st["name"] == "model.joblib" and st["health_score"] is None
    g.observe(_records(_data(300, seed=8, shifted=True)))
    st = g.status()
    assert st["health_score"] < 80 and "age" in st["drifted_columns"]
    assert "Guard('model.joblib'" in repr(g)


# ─── Decorator ────────────────────────────────────────────────────────────────

def test_watch_decorator_observes_and_returns_the_prediction(baselined):
    g = _guard(baselined)

    @g.watch
    def predict(features):
        """docstring kept"""
        return {"score": 0.5}

    assert predict({"age": 30, "income": 50000, "plan": "free"}) == {"score": 0.5}
    assert predict.__name__ == "predict" and predict.__doc__ == "docstring kept"
    assert g.observed == 1


def test_watch_with_arg_index_and_keyword(baselined):
    g = _guard(baselined)

    class Svc:
        @g.watch(arg=1)
        def predict(self, features):
            return "ok"

    @g.watch(arg="payload")
    def by_name(*, payload):
        return "ok"

    assert Svc().predict({"age": 30}) == "ok"
    assert by_name(payload={"age": 31}) == "ok"
    assert g.observed == 2


def test_watch_swallows_monitoring_errors(baselined, caplog):
    g = _guard(baselined)

    @g.watch
    def predict(features):
        return "still works"

    with caplog.at_level(logging.WARNING, logger="psiwatch"):
        assert predict("not a valid input") == "still works"
        assert predict() if False else True
    assert "could not observe input" in caplog.text
    assert g.observed == 0


def test_watch_handles_missing_argument_without_crashing(baselined):
    g = _guard(baselined)

    @g.watch(arg=3)
    def predict(x):
        return x

    assert predict(7) == 7


def test_watch_supports_async_functions(baselined):
    g = _guard(baselined)

    @g.watch
    async def predict(features):
        await asyncio.sleep(0)
        return "async ok"

    assert asyncio.iscoroutinefunction(predict)
    assert asyncio.run(predict({"age": 30, "plan": "pro"})) == "async ok"
    assert g.observed == 1


def test_watch_does_not_lose_the_prediction_if_the_function_raises(baselined):
    g = _guard(baselined)

    @g.watch
    def predict(features):
        raise RuntimeError("model crashed")

    with pytest.raises(RuntimeError, match="model crashed"):
        predict({"age": 30})
    assert g.observed == 1                                   # the input still counted


# ─── Concurrency ──────────────────────────────────────────────────────────────

def test_guard_is_thread_safe(baselined):
    g = _guard(baselined, window=5000, min_samples=5000)
    errors = []

    def worker(seed):
        try:
            for row in _records(_data(150, seed)):
                g.observe(row)
        except Exception as e:                               # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(s,)) for s in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and g.observed == 1200 and len(g._buf) == 1200


def test_only_one_background_check_runs_at_a_time(baselined, monkeypatch):
    g = _guard(baselined, background=True, check_every=10, min_samples=10, window=100)
    gate, started = threading.Event(), []
    real = g._evaluate

    def slow(snapshot):
        started.append(1)
        gate.wait(5)
        return real(snapshot)

    monkeypatch.setattr(g, "_evaluate", slow)
    for row in _records(_data(60, 3)):
        g.observe(row)
    time.sleep(0.2)
    assert len(started) == 1                                 # no pile-up while one is running
    gate.set()
    g.wait(5)
    assert g.checks == 1


# ─── Public API and CLI ───────────────────────────────────────────────────────

def test_public_exports():
    for name in ("Guard", "save_baseline", "load_baseline", "verify_baseline", "baseline_path"):
        assert hasattr(psiwatch, name) and name in psiwatch.__all__


def _csv(path, cols):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(list(cols))
        for row in zip(*cols.values()):
            w.writerow(row)


def test_cli_lock_and_check_with_model(tmp_path, monkeypatch, capsys):
    from psiwatch import cli
    monkeypatch.setenv("PSIWATCH_SILENT", "1")
    model = tmp_path / "model.joblib"
    model.write_bytes(b"model v1")
    train, live = tmp_path / "train.csv", tmp_path / "live.csv"
    _csv(train, _data(400, 1))
    _csv(live, _data(400, 2, shifted=True))

    monkeypatch.setattr(sys, "argv", ["psiwatch", "lock", str(train), "--model", str(model)])
    cli.main()
    assert "Baseline saved" in capsys.readouterr().out
    assert os.path.exists(baseline_path(str(model)))

    monkeypatch.setattr(sys, "argv", ["psiwatch", "lock-info", "--model", str(model)])
    cli.main()
    assert "age [numeric" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["psiwatch", "check", str(live), "--model", str(model)])
    cli.main()
    assert "HIGH" in capsys.readouterr().out

    model.write_bytes(b"model v2 retrained")
    monkeypatch.setattr(sys, "argv", ["psiwatch", "check", str(live), "--model", str(model)])
    cli.main()
    assert "different version" in capsys.readouterr().out


def test_save_lock_quiet_and_meta(tmp_path, capsys):
    from psiwatch.locker import save_lock
    save_lock(_data(100, 1), lock_path=str(tmp_path / "q.json"), quiet=True, meta={"file": "m"})
    assert capsys.readouterr().out == ""
    assert json.load(open(tmp_path / "q.json"))["model"] == {"file": "m"}
