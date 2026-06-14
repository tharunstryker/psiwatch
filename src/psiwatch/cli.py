"""
cli.py — Command-line interface for psiwatch.

Usage:
    psiwatch compare old.csv new.csv
    psiwatch compare old.csv new.csv --output report.html
    psiwatch compare old.csv new.csv --output report.json
    psiwatch compare old.csv new.csv --columns age,score
    psiwatch compare old.csv new.csv --psi-threshold 0.15
"""

import argparse
import sys
from . import compare


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
        """
    )

    subparsers = parser.add_subparsers(dest='command')

    # compare subcommand
    compare_parser = subparsers.add_parser(
        'compare',
        help='Compare two CSV files for data drift'
    )
    compare_parser.add_argument('old', help='Path to old/baseline CSV file')
    compare_parser.add_argument('new', help='Path to new/current CSV file')
    compare_parser.add_argument(
        '--output', '-o',
        help='Save report to file (.json, .txt, .html)',
        default=None
    )
    compare_parser.add_argument(
        '--columns', '-c',
        help='Comma-separated list of columns to compare (default: all)',
        default=None
    )
    compare_parser.add_argument(
        '--psi-threshold',
        type=float,
        default=None,
        metavar='FLOAT',
        help=(
            'PSI value to treat as HIGH drift boundary (default: 0.25). '
            'Medium threshold is auto-scaled to ~40%% of this value. '
            'Example: --psi-threshold 0.15'
        )
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == 'compare':
        columns = [c.strip() for c in args.columns.split(',')] if args.columns else None
        psi_threshold = args.psi_threshold

        try:
            compare(
                args.old,
                args.new,
                output=args.output,
                columns=columns,
                psi_threshold=psi_threshold,
            )
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
