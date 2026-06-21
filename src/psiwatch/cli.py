"""
cli.py — Command-line interface for psiwatch.

Commands:
    psiwatch compare old.csv new.csv [options]
    psiwatch summary old.csv new.csv
    psiwatch trend f1.csv f2.csv f3.csv [--baseline first|previous] [--output trend.html]
    psiwatch watch data/ [--lock file] [--once] [--webhook url] [--interval N]
    psiwatch lock train.csv [--output lock.json]
    psiwatch check new.csv [--lock lock.json] [--fail-on-drift]
    psiwatch lock-info [--lock lock.json]
    psiwatch init [--path psiwatch.toml]
    psiwatch update
    psiwatch version
"""

import argparse
import json
import sys
import os
from . import compare, analyze, DriftDetected, __version__
from .updater import do_upgrade, check_for_update


def _load_cfg():
    from .config import load_config
    return load_config(silent=True)


def _apply(cfg, args):
    from .config import apply_config
    return apply_config(args, cfg)


def _parse_list(val):
    return [c.strip() for c in val.split(",")] if val else None


def _summary_command(args):
    try:
        result = analyze(
            args.old, args.new,
            columns=_parse_list(args.columns),
            ignore_columns=_parse_list(getattr(args, "ignore_columns", None)),
            psi_threshold=args.psi_threshold,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    s = result["summary"]
    health = result["health_score"]
    icon = "[OK] " if health >= 80 else "[~]  " if health >= 50 else "[!!] "
    status = "Healthy" if health >= 80 else "Moderate Drift" if health >= 50 else "Significant Drift"

    print(f"\n  {icon} Health: {health}/100 — {status}")
    print(f"  Columns: {s['total_columns']} total  |  "
          f"HIGH: {s['high_count']}  MEDIUM: {s['medium_count']}  PASS: {s['pass_count']}")
    print(f"  Drifted: {', '.join(s['drifted_columns']) or 'none'}")
    for w in result["warnings"]:
        print(f"  ⚠  {w}")
    print()

    if args.fail_on_drift and health < 80:
        sys.exit(1)


def _trend_command(args):
    from .trend import analyze_trend, output_trend

    if len(args.files) < 2:
        print("  ERROR: trend requires at least 2 files")
        sys.exit(1)

    try:
        result = analyze_trend(
            args.files,
            columns=_parse_list(args.columns),
            ignore_columns=_parse_list(getattr(args, "ignore_columns", None)),
            psi_threshold=args.psi_threshold,
            baseline=getattr(args, "baseline_mode", "previous"),
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    output_trend(result, output=getattr(args, "output", None))


def _learn_thresholds_command(args):
    from .adapt import learn_thresholds, save_thresholds, print_learned_thresholds

    if not args.files and not args.directory:
        print("  ERROR: learn-thresholds requires file paths and/or --dir")
        sys.exit(1)

    try:
        result = learn_thresholds(
            files=args.files or None,
            directory=args.directory,
            pattern=args.pattern,
            columns=_parse_list(args.columns),
            ignore_columns=_parse_list(getattr(args, "ignore_columns", None)),
            sensitivity=args.sensitivity,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    print_learned_thresholds(result)
    save_thresholds(result, args.output)
    print(f"  Saved → {args.output}\n")


def _watch_command(args):
    from .watcher import watch_directory

    try:
        watch_directory(
            args.directory,
            lock_path=getattr(args, "lock", None),
            interval=getattr(args, "interval", None) or 60,
            once=getattr(args, "once", False),
            columns=_parse_list(args.columns),
            ignore_columns=_parse_list(getattr(args, "ignore_columns", None)),
            psi_threshold=args.psi_threshold,
            fail_on_drift=args.fail_on_drift,
            output_dir=getattr(args, "output_dir", None),
            webhook=getattr(args, "webhook", None),
        )
    except DriftDetected as e:
        print(f"\n  [FAIL] {e}")
        sys.exit(1)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)


def main():
    cfg = _load_cfg()

    parser = argparse.ArgumentParser(
        prog="psiwatch",
        description="Dataset drift detection — compare, watch, trend, lock.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  compare     Full drift report between two CSVs
  summary     One-line health score (no full report)
  trend       Compare multiple snapshots over time
  watch       Monitor a directory for new CSV files
  lock        Save a statistical baseline fingerprint
  check       Compare a CSV against a saved lock
  lock-info   Show what's in a lock file
  init        Create an example psiwatch.toml
  update      Upgrade psiwatch to latest
  version     Show installed version

Examples:
  psiwatch compare train.csv new.csv
  psiwatch compare train.csv new.csv --output report.html --fail-on-drift
  psiwatch compare train.csv new.csv --ignore-columns id,timestamp --format json
  psiwatch summary train.csv new.csv
  psiwatch trend w1.csv w2.csv w3.csv --output trend.html
  psiwatch trend w1.csv w2.csv w3.csv --baseline first
  psiwatch watch data/ --lock train.lock.json --once
  psiwatch watch data/ --webhook https://hooks.slack.com/... --fail-on-drift
  psiwatch lock train.csv && psiwatch check new.csv --fail-on-drift
  psiwatch init
        """
    )

    sub = parser.add_subparsers(dest="command")

    # ── version ──
    sub.add_parser("version", help="Show installed version")

    # ── update ──
    sub.add_parser("update", help="Upgrade to latest from PyPI")

    # ── init ──
    ip = sub.add_parser("init", help="Create an example psiwatch.toml")
    ip.add_argument("--path", default="psiwatch.toml")

    # ── shared column args ──
    def _add_col_args(p, with_two_files=True):
        if with_two_files:
            p.add_argument("old", help="Baseline CSV")
            p.add_argument("new", help="New CSV")
        p.add_argument("--columns", "-c", default=None,
                       help="Comma-separated columns to compare")
        p.add_argument("--ignore-columns", "-x", default=None,
                       help="Comma-separated columns to skip")
        p.add_argument("--psi-threshold", type=float, default=None, metavar="FLOAT")
        p.add_argument("--fail-on-drift", action="store_true", default=False,
                       help="Exit code 1 if drift detected")
        p.add_argument("--silent", action="store_true", default=False,
                       help="Suppress update banner")

    # ── compare ──
    cp = sub.add_parser("compare", help="Full drift report between two CSVs")
    _add_col_args(cp)
    cp.add_argument("--output", "-o", default=None,
                    help="Save report (.json, .txt, .html)")
    cp.add_argument("--format", "-f", choices=["terminal", "json", "txt", "html"],
                    default=None, help="Output format to stdout")
    cp.add_argument("--webhook", "-w", default=None,
                    help="Send alert to webhook after compare")
    cp.add_argument("--thresholds-file", default=None,
                    help="Use per-column learned thresholds from learn-thresholds")

    # ── summary ──
    sp = sub.add_parser("summary", help="One-line health score")
    _add_col_args(sp)

    # ── trend ──
    tp = sub.add_parser("trend", help="Compare multiple snapshots over time")
    tp.add_argument("files", nargs="+", help="CSV files (first = baseline)")
    tp.add_argument("--output", "-o", default=None,
                    help="Save trend report (.html or .json)")
    tp.add_argument("--baseline-mode", choices=["previous", "first"],
                    default="previous",
                    help="'previous': each vs prior. 'first': all vs first. (default: previous)")
    tp.add_argument("--columns", "-c", default=None)
    tp.add_argument("--ignore-columns", "-x", default=None)
    tp.add_argument("--psi-threshold", type=float, default=None)

    # ── learn-thresholds ──
    ltp = sub.add_parser("learn-thresholds",
                          help="Learn per-column drift thresholds from historical snapshots")
    ltp.add_argument("files", nargs="*", default=[],
                      help="CSV files, chronological order (at least 2, unless --dir is used)")
    ltp.add_argument("--dir", dest="directory", default=None,
                      help="Folder of snapshot files to include (sorted by filename)")
    ltp.add_argument("--pattern", default="*.csv",
                      help="Glob pattern used with --dir (default: *.csv)")
    ltp.add_argument("--output", "-o", default="psiwatch_thresholds.json",
                      help="Where to save learned thresholds (default: psiwatch_thresholds.json)")
    ltp.add_argument("--sensitivity", type=float, default=3.0,
                      help="mean + N*std multiplier — higher = more lenient (default: 3.0)")
    ltp.add_argument("--columns", "-c", default=None)
    ltp.add_argument("--ignore-columns", "-x", default=None)

    # ── watch ──
    wp = sub.add_parser("watch", help="Monitor a directory for new CSV files")
    wp.add_argument("directory", help="Directory to watch")
    wp.add_argument("--lock", "-l", default=None,
                    help="Lock file (default: psiwatch.lock.json)")
    wp.add_argument("--interval", "-i", type=int, default=None,
                    help="Poll interval in seconds (default: 60)")
    wp.add_argument("--once", action="store_true", default=False,
                    help="Single pass then exit — designed for cron/CI")
    wp.add_argument("--webhook", "-w", default=None,
                    help="Webhook URL for drift alerts")
    wp.add_argument("--output-dir", default=None,
                    help="Save HTML report here for each drifted file")
    wp.add_argument("--columns", "-c", default=None)
    wp.add_argument("--ignore-columns", "-x", default=None)
    wp.add_argument("--psi-threshold", type=float, default=None)
    wp.add_argument("--fail-on-drift", action="store_true", default=False)

    # ── lock ──
    lp = sub.add_parser("lock", help="Save a statistical baseline lock")
    lp.add_argument("file", help="CSV to lock")
    lp.add_argument("--output", "-o", default="psiwatch.lock.json")
    lp.add_argument("--columns", "-c", default=None)

    # ── check ──
    ckp = sub.add_parser("check", help="Compare a CSV against a lock file")
    ckp.add_argument("file", help="New CSV to check")
    ckp.add_argument("--lock", "-l", default="psiwatch.lock.json")
    ckp.add_argument("--output", "-o", default=None)
    ckp.add_argument("--columns", "-c", default=None)
    ckp.add_argument("--ignore-columns", "-x", default=None)
    ckp.add_argument("--psi-threshold", type=float, default=None)
    ckp.add_argument("--fail-on-drift", action="store_true", default=False)
    ckp.add_argument("--webhook", "-w", default=None,
                     help="Send alert to webhook if drift detected")

    # ── lock-info ──
    lip = sub.add_parser("lock-info", help="Show what's in a lock file")
    lip.add_argument("--lock", "-l", default="psiwatch.lock.json")

    # ── dispatch ──
    args = parser.parse_args()
    _apply(cfg, args)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "version":
        print(f"psiwatch {__version__}")
        sys.exit(0)

    if args.command == "update":
        sys.exit(do_upgrade())

    # v0.12.0: the PyPI version-check banner now only fires from the CLI
    # (never on `import psiwatch`). --silent or PSIWATCH_SILENT=1 / CI=true
    # env vars suppress it; check_for_update() already handles the latter.
    if not getattr(args, "silent", False):
        try:
            check_for_update(__version__)
        except Exception:
            pass

    if args.command == "init":
        from .config import write_example_config
        write_example_config(path=args.path)
        return

    if args.command == "summary":
        _summary_command(args)
        return

    if args.command == "trend":
        _trend_command(args)
        return

    if args.command == "learn-thresholds":
        _learn_thresholds_command(args)
        return

    if args.command == "watch":
        _watch_command(args)
        return

    if args.command == "lock":
        from .locker import save_lock
        try:
            save_lock(args.file, lock_path=args.output,
                      columns=_parse_list(args.columns))
        except FileNotFoundError as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        return

    if args.command == "check":
        from .locker import load_lock
        from .webhook import send_webhook
        try:
            result = load_lock(
                args.file, lock_path=args.lock, output=args.output,
                columns=_parse_list(args.columns),
                ignore_columns=_parse_list(getattr(args, "ignore_columns", None)),
                psi_threshold=args.psi_threshold,
                fail_on_drift=args.fail_on_drift,
            )
            if getattr(args, "webhook", None):
                send_webhook(args.webhook, result,
                             source_info=os.path.basename(args.file))
        except DriftDetected as e:
            print(f"\n  [FAIL] {e}")
            sys.exit(1)
        except (FileNotFoundError, ValueError) as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        return

    if args.command == "lock-info":
        from .locker import lock_info
        lock_info(lock_path=args.lock)
        return

    if args.command == "compare":
        output_path = args.output
        fmt = getattr(args, "format", None)
        _using_tmp = False

        if fmt and fmt != "terminal" and not output_path:
            import tempfile
            ext = {"json": ".json", "txt": ".txt", "html": ".html"}[fmt]
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="w")
            tmp.close()
            output_path = tmp.name
            _using_tmp = True

        try:
            if getattr(args, "thresholds_file", None):
                from .adapt import compare_with_learned_thresholds
                result = compare_with_learned_thresholds(
                    args.old, args.new, args.thresholds_file,
                    columns=_parse_list(args.columns),
                    ignore_columns=_parse_list(getattr(args, "ignore_columns", None)),
                )
                print(f"\n  Adaptive thresholds used for: "
                      f"{', '.join(result['adaptive_columns']) or '(none matched)'}")
                print(f"  Health Score: {result['health_score']}/100")
                print(f"  Drifted columns: {result['summary']['drifted_columns'] or 'none'}\n")
                if output_path:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2)
                    print(f"  Saved → {output_path}\n")
                if args.fail_on_drift and result["health_score"] < 80:
                    sys.exit(1)
            else:
                result = compare(
                    args.old, args.new,
                    output=output_path,
                    columns=_parse_list(args.columns),
                    ignore_columns=_parse_list(getattr(args, "ignore_columns", None)),
                    psi_threshold=args.psi_threshold,
                    fail_on_drift=args.fail_on_drift,
                    silent_update=getattr(args, "silent", False),
                    silent_save=_using_tmp,
                )

            if fmt and fmt != "terminal" and output_path and not args.output:
                import sys as _sys
                with open(output_path, "r", encoding="utf-8") as f:
                    _sys.stdout.write(f.read())
                os.unlink(output_path)

            # Webhook on compare
            if getattr(args, "webhook", None):
                from .webhook import send_webhook
                send_webhook(args.webhook, result,
                             source_info=f"{args.old} → {args.new}")

        except DriftDetected as e:
            print(f"\n  [FAIL] {e}")
            sys.exit(1)
        except (FileNotFoundError, ValueError) as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
