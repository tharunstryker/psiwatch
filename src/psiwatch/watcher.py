"""
watcher.py — Directory watch mode for psiwatch.

Polls a directory for new or modified CSV files and checks each one
against a baseline lock file as it appears.

State persistence:
    Seen files are tracked by filename → mtime in <lock_path>.seen.json.
    A file is reprocessed only if it is new OR its mtime has changed.
    This means --once in cron/CI never reprocesses old unchanged files,
    but DOES reprocess a file that was modified since last check.

    If no lock file exists yet, the first CSV file found is automatically
    locked as the baseline.

Usage:
    psiwatch watch data/
    psiwatch watch data/ --lock train.lock.json
    psiwatch watch data/ --interval 30
    psiwatch watch data/ --once
    psiwatch watch data/ --webhook https://hooks.slack.com/services/XXX
    psiwatch watch data/ --fail-on-drift
    psiwatch watch data/ --output-dir reports/

    # Python
    from psiwatch.watcher import watch_directory
    watch_directory("data/", once=True)
    watch_directory("data/", lock_path="train.lock.json", webhook="https://...")
"""

import glob
import json
import os
import time
from datetime import datetime


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _list_csv_files(directory):
    return sorted(glob.glob(os.path.join(directory, "*.csv")))


def _state_path(lock_path):
    return lock_path + ".seen.json"


def _load_state(lock_path):
    path = _state_path(lock_path)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(lock_path, state):
    path = _state_path(lock_path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError:
        pass


def watch_directory(directory, lock_path=None, interval=60, once=False,
                    columns=None, ignore_columns=None, psi_threshold=None,
                    thresholds=None, webhook=None, fail_on_drift=False,
                    output_dir=None):
    """
    Watch a directory for new/modified CSV files and check each against a lock.

    Args:
        directory: path to a directory containing CSV files
        lock_path: path to the lock file (default: psiwatch.lock.json).
                   If it doesn't exist, the first CSV found is auto-locked.
        interval: seconds between polls (ignored if once=True)
        once: check current files once and return — designed for cron/CI.
              Persists seen-file state so repeated runs skip unchanged files.
        columns: optional list of columns to compare
        ignore_columns: optional list of columns to skip
        psi_threshold: PSI HIGH boundary override
        thresholds: dict of threshold overrides
        webhook: Slack/Discord/generic webhook URL for drift alerts
        fail_on_drift: raise DriftDetected after run if any file drifted
        output_dir: save an HTML report here for each drifted file

    Returns:
        dict:
            'processed'     — number of files checked this run
            'results'       — {filename: result_dict}
            'drifted_files' — list of filenames where drift was detected

    Raises:
        FileNotFoundError: if directory doesn't exist
        DriftDetected: if fail_on_drift=True and any file drifted
    """
    from .locker import save_lock, load_lock, DEFAULT_LOCK_FILE
    from .reporter import to_html
    from .webhook import send_webhook
    from . import DriftDetected

    if not os.path.isdir(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")

    lock_path = lock_path or DEFAULT_LOCK_FILE
    state = _load_state(lock_path)
    results = {}
    drifted_files = []

    print(f"\n  psiwatch watch — {directory}")
    print(f"  Lock: {lock_path}")
    if output_dir:
        print(f"  Reports: {output_dir}")
    if webhook:
        print(f"  Webhook: {webhook}")
    if once:
        print("  Mode: single pass (--once)\n")
    else:
        print(f"  Interval: {interval}s — press Ctrl+C to stop\n")

    # Auto-lock first file if no lock exists yet
    if not os.path.exists(lock_path):
        existing = _list_csv_files(directory)
        if existing:
            first = existing[0]
            print(f"  [{_now()}] No lock found — locking baseline: {os.path.basename(first)}")
            save_lock(first, lock_path=lock_path, columns=columns)
            state[first] = os.path.getmtime(first)
            _save_state(lock_path, state)
        else:
            print(f"  [{_now()}] No lock and directory empty — waiting for first file.")

    def _process_pass():
        files = _list_csv_files(directory)

        # If still no lock (directory was empty), try auto-locking now
        if not os.path.exists(lock_path):
            unseen = [f for f in files if f not in state]
            if unseen:
                first = unseen.pop(0)
                print(f"  [{_now()}] Locking baseline: {os.path.basename(first)}")
                save_lock(first, lock_path=lock_path, columns=columns)
                state[first] = os.path.getmtime(first)

        for fpath in files:
            mtime = os.path.getmtime(fpath)
            if state.get(fpath) == mtime:
                continue  # seen and unchanged — skip

            name = os.path.basename(fpath)
            is_modified = fpath in state
            tag = "modified" if is_modified else "new"
            print(f"  [{_now()}] [{tag}] {name}")

            try:
                result = load_lock(
                    fpath, lock_path=lock_path,
                    columns=columns, ignore_columns=ignore_columns,
                    psi_threshold=psi_threshold, thresholds=thresholds,
                )
                results[name] = result
                health = result["health_score"]
                s = result["summary"]

                if health >= 80:
                    print(f"    [OK]  {health}/100 — Stable")
                elif health >= 50:
                    print(f"    [~]   {health}/100 — Moderate Drift")
                    if s["drifted_columns"]:
                        print(f"          Drifted: {', '.join(s['drifted_columns'])}")
                else:
                    print(f"    [!!]  {health}/100 — Significant Drift")
                    if s["drifted_columns"]:
                        print(f"          HIGH/MEDIUM: {', '.join(s['drifted_columns'])}")

                if health < 80:
                    drifted_files.append(name)

                # HTML report
                if output_dir and health < 80:
                    os.makedirs(output_dir, exist_ok=True)
                    stem = os.path.splitext(name)[0]
                    rpath = os.path.join(output_dir, f"{stem}_drift.html")
                    to_html(result, filepath=rpath, source_info=f"watch: {name}")
                    print(f"    Report → {rpath}")

                # Webhook
                if webhook:
                    sent = send_webhook(webhook, result, source_info=name)
                    if sent:
                        print("    [webhook] alert sent")

            except Exception as e:
                print(f"    [ERROR] {e}")

            state[fpath] = mtime

    try:
        if once:
            _process_pass()
        else:
            while True:
                _process_pass()
                time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n  [{_now()}] Watch stopped.")
    finally:
        _save_state(lock_path, state)

    if fail_on_drift and drifted_files:
        from . import DriftDetected
        raise DriftDetected(
            f"Drift detected in {len(drifted_files)} file(s): {drifted_files}"
        )

    return {
        "processed": len(results),
        "results": results,
        "drifted_files": drifted_files,
    }


# Alias for backwards compatibility with my earlier API
def watch(directory, baseline=None, lock_path=None, interval=60,
          columns=None, ignore_columns=None, psi_threshold=None,
          thresholds=None, fail_on_drift=False, output_dir=None,
          webhook_url=None):
    """
    Alias for watch_directory(). Accepts baseline= as an alternative to lock_path.
    If baseline is given and no lock exists, auto-locks it first.
    """
    from .locker import save_lock, DEFAULT_LOCK_FILE

    resolved_lock = lock_path or DEFAULT_LOCK_FILE

    if baseline and not os.path.exists(resolved_lock):
        save_lock(baseline, lock_path=resolved_lock, columns=columns)

    return watch_directory(
        directory,
        lock_path=resolved_lock,
        interval=interval,
        columns=columns,
        ignore_columns=ignore_columns,
        psi_threshold=psi_threshold,
        thresholds=thresholds,
        webhook=webhook_url,
        fail_on_drift=fail_on_drift,
        output_dir=output_dir,
    )
