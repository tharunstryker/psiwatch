"""
cli.py — Command-line interface for psiwatch.

Usage:
    psiwatch compare old.csv new.csv
    psiwatch compare old.csv new.csv --output report.html
    psiwatch compare old.csv new.csv --columns age,score
    psiwatch compare old.csv new.csv --psi-threshold 0.15
    psiwatch compare old.csv new.csv --fail-on-drift
    psiwatch update
    psiwatch version
"""

import argparse
import sys
from . import compare, DriftDetected, __version__


def main():
    parser = argparse.ArgumentParser(
        prog='psiwatch',
        description='Dataset drift detection — compare old vs new data.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  psiwatch compare train.csv new.csv
  psiwatch compare train.csv new.csv --output report.html
  psiwatch compare train.csv new.csv --output report.json
  psiwatch compare train.csv new.csv --columns age,score,city
  psiwatch compare train.csv new.csv --psi-threshold 0.15
  psiwatch compare train.csv new.csv --fail-on-drift
  psiwatch update
  psiwatch version
        """
    )

    subparsers = parser.add_subparsers(dest='command')

    # version
    subparsers.add_parser('version', help='Show installed psiwatch version')

    # update — self-upgrade from PyPI
    subparsers.add_parser('update', help='Upgrade psiwatch to latest version from PyPI')

    # compare
    compare_parser = subparsers.add_parser(
        'compare',
        help='Compare two CSV files for data drift'
    )
    compare_parser.add_argument('old', help='Path to old/baseline CSV file')
    compare_parser.add_argument('new', help='Path to new/current CSV file')
    compare_parser.add_argument('--output', '-o', help='Save report (.json/.txt/.html)', default=None)
    compare_parser.add_argument('--columns', '-c', help='Comma-separated columns to compare', default=None)
    compare_parser.add_argument(
        '--psi-threshold', type=float, default=None, metavar='FLOAT',
        help='PSI HIGH boundary (default 0.25). Medium auto-scales to 40%%.'
    )
    compare_parser.add_argument(
        '--fail-on-drift', action='store_true', default=False,
        help='Exit code 1 if health_score < 80. Use in CI/CD pipelines.'
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == 'version':
        print(f"psiwatch {__version__}")
        sys.exit(0)

    if args.command == 'update':
        from .updater import run_self_update
        success = run_self_update()
        sys.exit(0 if success else 1)

    if args.command == 'compare':
        columns = [c.strip() for c in args.columns.split(',')] if args.columns else None

        try:
            compare(
                args.old,
                args.new,
                output=args.output,
                columns=columns,
                psi_threshold=args.psi_threshold,
                fail_on_drift=args.fail_on_drift,
            )
        except DriftDetected as e:
            print(f"\n  [FAIL] {e}")
            sys.exit(1)
        except FileNotFoundError as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n  ERROR: Unexpected error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
