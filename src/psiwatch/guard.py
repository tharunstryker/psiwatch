"""
guard.py — Drift guard for deployed models (v0.16.0).

Two things pickle / joblib don't do for you:

1. A saved model doesn't carry a fingerprint of the data it was trained on.
   save_baseline() writes one next to the model file:

       joblib.dump(model, "model.joblib")
       psiwatch.save_baseline(X_train, "model.joblib")   # -> model.joblib.psiwatch.json

   The baseline records the model file's SHA-256, so psiwatch can tell when a
   baseline belongs to an older version of the model.

2. Nothing watches the live inputs. Guard keeps a rolling window of what your
   model is actually receiving, compares it to the baseline, and alerts when
   it drifts:

       guard = psiwatch.Guard.from_model("model.joblib", webhook=SLACK_URL)

       @guard.watch                      # Flask / FastAPI / any function
       def predict(features): ...

Design rules
------------
* Pure standard library. No dependency on joblib, scikit-learn, Flask or
  FastAPI — Guard only needs rows (dicts, DataFrames, or arrays + names).
* Serving never waits on monitoring: drift checks and alerts run in a
  background thread by default.
* Monitoring never breaks a prediction: @guard.watch swallows (and logs)
  its own errors.
* Thread-safe: safe to call from multi-threaded web servers.
* None / NaN values are treated as missing and skipped, the same way pandas
  NaN is skipped when a baseline is built from a DataFrame.
"""

import functools
import hashlib
import inspect
import logging
import os
import random
import threading
import time
import warnings
from collections import deque

log = logging.getLogger("psiwatch")
log.addHandler(logging.NullHandler())

SIDECAR_SUFFIX = ".psiwatch.json"
_ALERT_RANK = {"MEDIUM": 1, "HIGH": 2}
_SEVERITY_RANK = {"PASS": 0, "UNKNOWN": 0, "MEDIUM": 1, "HIGH": 2}


# ─── Input handling ───────────────────────────────────────────────────────────

def _missing(v):
    if v is None:
        return True
    try:
        return bool(v != v)          # NaN (float / numpy); pd.NA raises → missing
    except Exception:
        return True


def _is_seq(v):
    return isinstance(v, (list, tuple)) or (
        hasattr(v, "tolist") and not isinstance(v, (str, bytes)))


def _to_list(v):
    return v.tolist() if hasattr(v, "tolist") else list(v)


def _clean_row(row):
    return {str(k): str(v) for k, v in row.items() if not _missing(v)}


def _rows_from(data, feature_names=None):
    """
    Normalise one observation or a batch into a list of {column: str} rows.

    Accepts: a dict (one row, or {column: [values]}), a list of dicts, a pandas
    DataFrame, or a 1-D / 2-D array-like (list, tuple, numpy array) together
    with feature_names.
    """
    if hasattr(data, "columns") and hasattr(data, "to_dict"):      # DataFrame
        return [_clean_row(r) for r in data.to_dict("records")]

    if isinstance(data, dict):
        if any(_is_seq(v) for v in data.values()):                  # columnar
            cols = {k: (_to_list(v) if _is_seq(v) else [v]) for k, v in data.items()}
            n = max(len(v) for v in cols.values())
            bad = [k for k, v in cols.items() if len(v) not in (1, n)]
            if bad:
                raise ValueError(f"Columns have different lengths: {bad}")
            return [_clean_row({k: (v[i] if len(v) > 1 else v[0]) for k, v in cols.items()})
                    for i in range(n)]
        return [_clean_row(data)]

    seq = data.tolist() if hasattr(data, "tolist") else data
    if isinstance(seq, (list, tuple)):
        if not seq:
            return []
        if isinstance(seq[0], dict):
            return [_clean_row(r) for r in seq]
        if feature_names is None:
            raise ValueError(
                "Array-like input needs feature names, e.g. "
                "Guard(..., features=['age', 'income']) or "
                "guard.observe(X, features=[...])."
            )
        names = list(feature_names)
        rows = seq if isinstance(seq[0], (list, tuple)) else [seq]
        out = []
        for r in rows:
            r = _to_list(r) if hasattr(r, "tolist") else list(r)
            if len(r) != len(names):
                raise ValueError(
                    f"Row has {len(r)} values but {len(names)} feature names were given."
                )
            out.append(_clean_row(dict(zip(names, r))))
        return out

    raise TypeError(
        f"Unsupported input type: {type(data).__name__}. Expected a dict, list of "
        f"dicts, DataFrame, or array-like with feature names."
    )


# ─── Model-attached baseline ──────────────────────────────────────────────────

def baseline_path(model_path):
    """Where the baseline for a model file lives: <model file>.psiwatch.json"""
    return os.fspath(model_path) + SIDECAR_SUFFIX


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _model_meta(model_path):
    from . import __version__
    meta = {"file": os.path.basename(os.fspath(model_path)),
            "psiwatch_version": __version__}
    if os.path.isfile(model_path):
        meta["size"] = os.path.getsize(model_path)
        meta["sha256"] = _sha256_file(model_path)
    return meta


def save_baseline(data, model_path, columns=None, ignore_columns=None,
                  text_columns=None, detect_text=True, feature_names=None,
                  quiet=False):
    """
    Save a statistical fingerprint of the training data next to a model file.

    Args:
        data: training data — DataFrame, dict, list of dicts, CSV path, or a
            2-D array-like together with feature_names.
        model_path: path of the saved model (e.g. "model.joblib"). The
            baseline is written to "<model_path>.psiwatch.json".
        columns / ignore_columns: restrict which columns are fingerprinted.
        text_columns / detect_text: free-text handling, as in compare().
        feature_names: column names, required for array-like data.
        quiet: suppress the confirmation messages.

    Returns:
        str — path of the baseline file.

    The baseline holds summary statistics only, never raw rows. (For text
    columns it stores word counts for the top 1,000 words.) If the model file
    exists, its SHA-256 is recorded so Guard.from_model() can warn when the
    baseline belongs to an older version of the model.
    """
    from .loader import resolve_input
    from .locker import save_lock

    if (not isinstance(data, (str, dict)) and not hasattr(data, "columns")
            and not (isinstance(data, list) and data and isinstance(data[0], dict))):
        rows = _rows_from(data, feature_names)
        cols = {}
        for r in rows:
            for k, v in r.items():
                cols.setdefault(k, []).append(v)
    else:
        cols = resolve_input(data)

    if ignore_columns:
        cols = {k: v for k, v in cols.items() if k not in set(ignore_columns)}

    path = baseline_path(model_path)
    save_lock(cols, lock_path=path, columns=columns, text_columns=text_columns,
              detect_text=detect_text, meta=_model_meta(model_path), quiet=True)
    if not quiet:
        print(f"  Baseline saved → {path}")
    return path


def verify_baseline(model_path):
    """
    Check that a model's baseline was created for this exact model file.

    Returns (status, message): status is True (match), False (the model file
    changed since the baseline was saved) or None (cannot tell — the model
    file is missing or the baseline recorded no hash).
    Raises FileNotFoundError if there is no baseline next to the model.
    """
    from .locker import read_lock

    path = baseline_path(model_path)
    lock = read_lock(path)
    meta = lock.get("model") or {}
    if "sha256" not in meta:
        return None, "Baseline has no model hash, so it can't be verified."
    if not os.path.isfile(model_path):
        return None, f"Model file {model_path} not found, so the baseline can't be verified."
    if _sha256_file(model_path) == meta["sha256"]:
        return True, "Baseline matches the model file."
    return False, (
        f"{os.path.basename(path)} was saved for a different version of "
        f"{meta.get('file', 'the model')}. If you retrained the model, re-run "
        f"psiwatch.save_baseline(X_train, {os.fspath(model_path)!r})."
    )


def load_baseline(model_path, verify=True):
    """Read the baseline saved next to a model (validated). Warns if it looks stale."""
    from .locker import read_lock

    path = baseline_path(model_path)
    if not os.path.exists(path):
        raise FileNotFoundError(_missing_baseline_message(model_path))
    if verify:
        ok, msg = verify_baseline(model_path)
        if ok is False:
            warnings.warn(msg, UserWarning, stacklevel=2)
    return read_lock(path)


def _missing_baseline_message(model_path):
    return (
        f"No baseline found next to the model: {baseline_path(model_path)}\n"
        f"Create it once after training:\n"
        f"    psiwatch.save_baseline(X_train, {os.fspath(model_path)!r})"
    )


# ─── Guard ────────────────────────────────────────────────────────────────────

class Guard:
    """
    Watches the live inputs of a deployed model and alerts when they drift
    from the training baseline.

        guard = Guard.from_model("model.joblib", webhook=SLACK_URL)

        @guard.watch
        def predict(features):          # features: dict / list of dicts / DataFrame
            return model.predict(...)

        # or, without the decorator:
        guard.observe(features)

    Args:
        baseline: path of a lock / baseline file, or a lock dict.
        features: feature names, for array-like input.
        window: how many recent rows to keep and compare (default 1000).
        min_samples: don't check until this many rows are in the window (100).
        check_every: re-check after this many new rows (default 100).
        alert_on: "HIGH" (default) or "MEDIUM" — lowest column severity that
            counts as drift.
        thresholds: threshold overrides (same keys as compare()).
        webhook: Slack / Discord / generic JSON URL, notified on drift.
        on_drift: callback(result) called on drift. Exceptions are logged.
        cooldown: seconds between repeated alerts for ongoing drift (3600).
            A recovery resets it, so a new incident alerts immediately.
        sample: fraction of rows to keep, 0-1 (default 1.0), for very high
            traffic.
        background: run checks and alerts in a background thread (default
            True) so serving never waits. Use False for deterministic tests.
        columns / ignore_columns: restrict which baseline columns are watched.
        name: label used in alerts (default: the baseline's model file name).
    """

    def __init__(self, baseline, features=None, window=1000, min_samples=100,
                 check_every=100, alert_on="HIGH", thresholds=None,
                 webhook=None, on_drift=None, cooldown=3600, sample=1.0,
                 background=True, columns=None, ignore_columns=None, name=None):
        from .locker import read_lock, _lock_to_summaries

        if alert_on not in _ALERT_RANK:
            raise ValueError("alert_on must be 'HIGH' or 'MEDIUM'")
        if window < 1 or check_every < 1 or min_samples < 1:
            raise ValueError("window, min_samples and check_every must be >= 1")
        if not 0 <= sample <= 1:
            raise ValueError("sample must be between 0 and 1")

        if isinstance(baseline, dict):
            lock, label = baseline, name or "baseline"
        else:
            lock = read_lock(os.fspath(baseline))
            label = name or (lock.get("model") or {}).get("file") \
                or os.path.basename(os.fspath(baseline))

        summaries = _lock_to_summaries(lock)
        if columns:
            summaries = {k: v for k, v in summaries.items() if k in set(columns)}
        if ignore_columns:
            summaries = {k: v for k, v in summaries.items()
                         if k not in set(ignore_columns)}
        if not summaries:
            raise ValueError("The baseline has no columns to watch.")

        self.name = label
        self._summaries = summaries
        self._known = set(summaries)
        self._base_counts = {
            c: (lock["columns"].get(c, {}).get("count")
                or summaries[c]["summary"].get("count"))
            for c in summaries
        }
        self._features = list(features) if features else None
        self._window = window
        self._min_samples = min(min_samples, window)
        self._check_every = check_every
        self._alert_on = alert_on
        self._thresholds = thresholds
        self._webhook = webhook
        self._on_drift = on_drift
        self._cooldown = cooldown
        self._sample = sample
        self._background = background

        self._buf = deque(maxlen=window)
        self._mutex = threading.Lock()
        self._worker = None
        self._since_check = 0
        self._last_alert = None
        self._observe_errors = 0

        self.observed = 0            # rows kept so far
        self.checks = 0              # drift checks completed
        self.alerts = 0              # alerts fired
        self.last_result = None      # most recent analyze() result
        self.last_checked_at = None  # epoch seconds

    @classmethod
    def from_model(cls, model_path, verify=True, **kwargs):
        """Build a Guard from the baseline saved next to a model file."""
        path = baseline_path(model_path)
        if not os.path.exists(path):
            raise FileNotFoundError(_missing_baseline_message(model_path))
        if verify:
            ok, msg = verify_baseline(model_path)
            if ok is False:
                warnings.warn(msg, UserWarning, stacklevel=2)
        kwargs.setdefault("name", os.path.basename(os.fspath(model_path)))
        return cls(path, **kwargs)

    # ── observing ────────────────────────────────────────────────────────────

    def observe(self, data, features=None):
        """
        Add one row or a batch of rows to the rolling window.

        Returns the number of rows kept (sampling may drop some). Raises
        ValueError / TypeError for input it can't use — @guard.watch catches
        these so monitoring never breaks serving.
        """
        rows = _rows_from(data, features or self._features)
        for r in rows:
            if self._known.isdisjoint(r):
                raise ValueError(
                    f"Input has none of the watched columns. Expected some of: "
                    f"{sorted(self._known)}; got: {sorted(r)}"
                )

        if self._sample < 1.0:
            rows = [r for r in rows if random.random() < self._sample]
        kept = [{k: v for k, v in r.items() if k in self._known} for r in rows]
        if not kept:
            return 0

        with self._mutex:
            self._buf.extend(kept)
            self.observed += len(kept)
            self._since_check += len(kept)
        self._maybe_check()
        return len(kept)

    def _maybe_check(self):
        with self._mutex:
            if len(self._buf) < self._min_samples or self._since_check < self._check_every:
                return
            if self._worker is not None and self._worker.is_alive():
                return                                     # a check is already running
            snapshot = list(self._buf)
            self._since_check = 0
            if self._background:
                self._worker = threading.Thread(
                    target=self._run_check, args=(snapshot,), daemon=True)
                self._worker.start()
                return
        self._run_check(snapshot)

    # ── checking ─────────────────────────────────────────────────────────────

    def _evaluate(self, snapshot):
        from . import _build_thresholds
        from .analyzer import analyze

        cols = {c: [] for c in self._known}
        for row in snapshot:
            for c, v in row.items():
                cols[c].append(v)
        t = _build_thresholds(psi_threshold=None, thresholds=self._thresholds)
        return analyze({}, cols, thresholds=t, baseline_summaries=self._summaries,
                       column_thresholds=self._noise_margins(cols, t))

    def _noise_margins(self, cols, t):
        """
        Per-column thresholds widened by the noise expected from comparing a
        SMALL live window with the baseline.

        PSI on a 200-row window of perfectly healthy data exceeds the usual
        0.25 "HIGH" line about 1 time in 100 and the 0.1 line about 1 time in 4
        (sparse tail bins). A guard that cries wolf gets switched off, so each
        column's PSI / mean-shift / std-shift / share-shift thresholds are
        raised by a margin that shrinks as the window grows. The empirical
        factor (5x the chi-square estimate below 1,000 rows, 2x above) comes
        from simulating healthy windows. Text columns have their own noise
        correction and are left alone.
        """
        from .analyzer import DEFAULT_THRESHOLDS
        t = {**DEFAULT_THRESHOLDS, **(t or {})}
        out = {}
        for c, vals in cols.items():
            n_new = len(vals)
            entry = self._summaries[c]
            if n_new == 0 or entry["type"] == "text":
                continue
            n_base = self._base_counts.get(c)
            inv = 1.0 / n_new + (1.0 / n_base if n_base else 0.0)
            f = 5.0 if n_new < 1000 else 2.0
            if entry["type"] == "numeric":
                se = inv ** 0.5
                psi_margin = f * 9 * inv                       # 10 bins -> 9 d.o.f.
                out[c] = {
                    "psi_medium": t["psi_medium"] + psi_margin,
                    "psi_high": t["psi_high"] + psi_margin,
                    "mean_shift_medium": t["mean_shift_medium"] + 2 * se,
                    "mean_shift_high": t["mean_shift_high"] + 2 * se,
                    "std_shift_medium": t["std_shift_medium"] + 2 * (inv / 2) ** 0.5,
                    "std_shift_high": t["std_shift_high"] + 2 * (inv / 2) ** 0.5,
                }
            else:                                              # categorical
                k = max(len(entry["summary"].get("categories", [])), 2)
                psi_margin = f * (k - 1) * inv
                out[c] = {
                    "psi_medium": t["psi_medium"] + psi_margin,
                    "psi_high": t["psi_high"] + psi_margin,
                    "category_share_shift":
                        t["category_share_shift"] + 2 * (0.25 * inv) ** 0.5,
                }
        return out

    def _run_check(self, snapshot):
        try:
            self._finish(self._evaluate(snapshot))
        except Exception as e:                              # never kill the worker
            log.warning("psiwatch: drift check failed: %s", e)

    def check(self):
        """
        Check the current window against the baseline right now (synchronously,
        regardless of min_samples) and return the analyze() result. Fires
        alerts the same way automatic checks do.
        """
        with self._mutex:
            snapshot = list(self._buf)
            self._since_check = 0
        if not snapshot:
            raise ValueError("Nothing observed yet — the window is empty.")
        result = self._evaluate(snapshot)
        self._finish(result)
        return result

    def _is_drift(self, result):
        need = _ALERT_RANK[self._alert_on]
        return any(_SEVERITY_RANK.get(r["severity"], 0) >= need
                   for r in result["columns"].values())

    def _finish(self, result):
        drifted = self._is_drift(result)
        now = time.monotonic()
        fire = False
        with self._mutex:
            self.last_result = result
            self.last_checked_at = time.time()
            self.checks += 1
            if drifted:
                if self._last_alert is None or now - self._last_alert >= self._cooldown:
                    self._last_alert = now
                    self.alerts += 1
                    fire = True
            else:
                self._last_alert = None                     # recovered
        if fire:
            self._alert(result)

    def _alert(self, result):
        from . import webhook as _wh

        label = f"live inputs of {self.name}"
        log.warning("psiwatch: drift detected in %s — health %s/100, drifted: %s",
                    self.name, result["health_score"],
                    ", ".join(result["summary"]["drifted_columns"]) or "none")
        if self._webhook:
            try:
                _wh.send_webhook(self._webhook, result, source_info=label, always=True)
            except Exception as e:                          # send_webhook shouldn't raise
                log.warning("psiwatch: webhook failed: %s", e)
        if self._on_drift:
            try:
                self._on_drift(result)
            except Exception:
                log.exception("psiwatch: on_drift callback raised")

    # ── decorator ────────────────────────────────────────────────────────────

    def watch(self, func=None, *, arg=0, features=None):
        """
        Decorator: observe the input of a prediction function.

            @guard.watch                       # first argument holds the features
            def predict(features): ...

            @guard.watch(arg=1)                # methods: arg 0 is self
            def predict(self, features): ...

            @guard.watch(arg="payload")        # or by keyword name

        Works for sync and async functions. The input is observed before the
        function runs; any monitoring error is logged and swallowed, so a
        prediction is never lost because of psiwatch.
        """
        def decorator(f):
            def _observe(args, kwargs):
                try:
                    if isinstance(arg, int):
                        if len(args) <= arg:
                            raise LookupError(f"no positional argument {arg}")
                        value = args[arg]
                    else:
                        value = kwargs[arg]
                    self.observe(value, features=features)
                except Exception as e:
                    self._observe_errors += 1
                    n = self._observe_errors
                    if n == 1 or n % 100 == 0:
                        log.warning("psiwatch: could not observe input of %s (%d errors): %s",
                                    getattr(f, "__name__", "function"), n, e)

            if inspect.iscoroutinefunction(f):
                @functools.wraps(f)
                async def wrapper(*args, **kwargs):
                    _observe(args, kwargs)
                    return await f(*args, **kwargs)
            else:
                @functools.wraps(f)
                def wrapper(*args, **kwargs):
                    _observe(args, kwargs)
                    return f(*args, **kwargs)
            return wrapper

        return decorator(func) if func is not None else decorator

    # ── state ────────────────────────────────────────────────────────────────

    def wait(self, timeout=None):
        """Block until a background check in progress (if any) finishes."""
        worker = self._worker
        if worker is not None:
            worker.join(timeout)

    def reset(self):
        """Clear the window and alert state (e.g. after deploying a new model)."""
        with self._mutex:
            self._buf.clear()
            self._since_check = 0
            self._last_alert = None

    def status(self):
        """Plain-dict snapshot of the guard's state — handy for a /health endpoint."""
        with self._mutex:
            result = self.last_result
            return {
                "name": self.name,
                "observed": self.observed,
                "window_rows": len(self._buf),
                "checks": self.checks,
                "alerts": self.alerts,
                "last_checked_at": self.last_checked_at,
                "health_score": result["health_score"] if result else None,
                "drifted_columns": (result["summary"]["drifted_columns"]
                                    if result else []),
                "drifting": self._last_alert is not None,
            }

    def __repr__(self):
        return (f"Guard({self.name!r}, columns={len(self._known)}, "
                f"window={self._window}, observed={self.observed}, "
                f"checks={self.checks}, alerts={self.alerts})")
