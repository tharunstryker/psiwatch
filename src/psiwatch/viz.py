"""
viz.py — Optional visual drift charts.

psiwatch's core stays zero-dependency. This module is the one deliberate
exception: it draws real histogram overlay charts (baseline vs new) using
matplotlib, but ONLY if you actually call plot_drift() — matplotlib is
imported lazily inside the function, not at module load time, so importing
psiwatch (or any other part of it) never requires matplotlib to be present.

Install the extra when you want this:
    pip install psiwatch[charts]
    # or just: pip install matplotlib

Why matplotlib and not seaborn: matplotlib alone is enough to draw an
overlaid histogram, and modern matplotlib ships several seaborn-derived
style sheets built in (e.g. "seaborn-v0_8", "seaborn-v0_8-darkgrid") — so
you get seaborn's visual style without psiwatch needing to import seaborn
itself. If you want actual seaborn-specific plot types (violin plots, KDE
grids, etc.) for your own custom visualization, install seaborn yourself
and work with psiwatch's raw analyze()/compare_data() result directly —
psiwatch doesn't broker that, by design, to keep its own footprint minimal.

Why this needs the RAW data, not just a result dict: analyze()/compare()
results only store summary statistics (mean, std, percentiles) — not the
original values — so there's no real distribution shape to plot from a
result dict alone. Approximating a shape from just mean+std would draw a
normal-distribution curve regardless of what the real data looks like,
which could actively mislead someone about their own data. plot_drift()
therefore takes the same baseline/new inputs you'd pass to compare()
(CSV path, dict, list of dicts, or DataFrame) and builds a REAL histogram
from the actual values, reusing the exact same binning logic the PSI
calculation itself uses (analyzer.build_numeric_histogram) — what you see
in the chart is what was actually used to compute the PSI you're looking
at, not a separate approximation.

Usage:
    import psiwatch
    from psiwatch.viz import plot_drift

    plot_drift("train.csv", "production.csv", output="drift.png")
    plot_drift("train.csv", "production.csv", columns=["age", "income"])
    plot_drift("train.csv", "production.csv", style="seaborn-v0_8-darkgrid")

    # CLI
    psiwatch compare train.csv production.csv --plot drift.png
"""

import os


def _require_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless backend — works in Termux/CI/servers with no display
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        raise ImportError(
            "plot_drift() requires matplotlib, which is not installed. "
            "Install it with: pip install matplotlib\n"
            "(or: pip install psiwatch[charts])"
        )


def _build_figure(old, new, columns=None, ignore_columns=None,
                   bins=10, style=None, max_cols_per_row=3,
                   figsize_per_plot=(4.5, 3.5), title=None):
    """
    Shared figure-building logic used by both plot_drift() (saves to file)
    and plot_drift_bytes() (returns PNG bytes, for HTML embedding). See
    plot_drift()'s docstring for what each argument does.
    """
    plt = _require_matplotlib()
    from .loader import resolve_input, cast_numeric, detect_type
    from .analyzer import build_numeric_histogram, _frequencies

    if style:
        if style not in plt.style.available:
            raise ValueError(
                f"Unknown matplotlib style '{style}'. Available styles: "
                f"{', '.join(plt.style.available)}"
            )
        plt.style.use(style)

    old_cols = resolve_input(old)
    new_cols = resolve_input(new)

    plot_columns = columns or [c for c in old_cols if c in new_cols]
    if ignore_columns:
        plot_columns = [c for c in plot_columns if c not in ignore_columns]
    plot_columns = [c for c in plot_columns if c in old_cols and c in new_cols]

    if not plot_columns:
        raise ValueError(
            "No columns to plot — check that 'old' and 'new' share column "
            "names, and that 'columns'/'ignore_columns' don't exclude everything."
        )

    n = len(plot_columns)
    ncols = min(max_cols_per_row, n)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(figsize_per_plot[0] * ncols, figsize_per_plot[1] * nrows),
        squeeze=False,
    )

    for i, col in enumerate(plot_columns):
        ax = axes[i // ncols][i % ncols]
        col_type = detect_type(old_cols[col])

        if col_type == "numeric":
            b_vals = cast_numeric(old_cols[col])
            n_vals = cast_numeric(new_cols[col])
            if len(b_vals) < 2 or len(n_vals) < 2:
                ax.set_title(f"{col} (insufficient data)")
                ax.axis("off")
                continue

            lo = min(min(b_vals), min(n_vals))
            hi = max(max(b_vals), max(n_vals))
            if lo == hi:
                hi = lo + 1  # avoid a zero-width range

            b_counts = build_numeric_histogram(b_vals, lo, hi, bins=bins)
            n_counts = build_numeric_histogram(n_vals, lo, hi, bins=bins)
            edges = [lo + k * (hi - lo) / bins for k in range(bins + 1)]
            centers = [(edges[k] + edges[k + 1]) / 2 for k in range(bins)]
            width = (hi - lo) / bins * 0.4

            ax.bar([c - width / 2 for c in centers], b_counts, width=width,
                   label="baseline", alpha=0.7)
            ax.bar([c + width / 2 for c in centers], n_counts, width=width,
                   label="new", alpha=0.7)
            ax.set_title(col)
            ax.legend(fontsize=8)

        else:
            b_freq = _frequencies([str(v) for v in old_cols[col]])
            n_freq = _frequencies([str(v) for v in new_cols[col]])
            all_cats = sorted(set(b_freq) | set(n_freq))
            if not all_cats:
                ax.set_title(f"{col} (no data)")
                ax.axis("off")
                continue

            b_vals_plot = [b_freq.get(c, 0) for c in all_cats]
            n_vals_plot = [n_freq.get(c, 0) for c in all_cats]
            x = range(len(all_cats))
            width = 0.4

            ax.bar([xi - width / 2 for xi in x], b_vals_plot, width=width,
                   label="baseline", alpha=0.7)
            ax.bar([xi + width / 2 for xi in x], n_vals_plot, width=width,
                   label="new", alpha=0.7)
            ax.set_xticks(list(x))
            ax.set_xticklabels(all_cats, rotation=45, ha="right", fontsize=7)
            ax.set_ylabel("proportion", fontsize=8)
            ax.set_title(col)
            ax.legend(fontsize=8)

    # Hide any unused grid cells (when columns don't evenly fill the grid)
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    fig.suptitle(title or "psiwatch — baseline vs new", fontsize=12)
    fig.tight_layout()
    return fig


def plot_drift(old, new, columns=None, ignore_columns=None,
                output="drift_chart.png", bins=10, style=None,
                max_cols_per_row=3, figsize_per_plot=(4.5, 3.5),
                title=None, dpi=120):
    """
    Draw real baseline-vs-new histogram overlays and save them to an image.

    Numeric columns get an overlaid histogram (baseline vs new, real binned
    data — the same bins PSI itself uses). Categorical columns get a
    side-by-side bar chart of category frequencies. One panel per column,
    arranged in a grid.

    Args:
        old: CSV path, Parquet path, dict, list of dicts, or DataFrame — baseline
        new: same types — new data
        columns: optional list — only plot these columns
        ignore_columns: optional list — skip these columns
        output: file path to save the chart. Extension controls format —
            anything matplotlib's savefig supports (.png, .pdf, .svg, .jpg).
        bins: number of histogram bins for numeric columns (default 10,
            matching analyzer.py's default PSI binning)
        style: optional matplotlib style name, e.g. "seaborn-v0_8",
            "seaborn-v0_8-darkgrid", "ggplot". See plt.style.available for
            the full list. None uses matplotlib's default style.
        max_cols_per_row: how many column-panels per row in the grid
        figsize_per_plot: (width, height) in inches for each panel
        title: optional custom title (default: "psiwatch — baseline vs new")
        dpi: output resolution in dots per inch (default 120; use 200+ for
            print/presentation quality, lower for smaller file sizes)

    Returns:
        The output file path (str), once saved.

    Raises:
        ImportError: matplotlib is not installed.
        ValueError: no columns to plot (after applying columns/ignore_columns
            and matching baseline/new schemas), or an unknown style name.
    """
    fig = _build_figure(
        old, new, columns=columns, ignore_columns=ignore_columns,
        bins=bins, style=style, max_cols_per_row=max_cols_per_row,
        figsize_per_plot=figsize_per_plot, title=title,
    )

    out_dir = os.path.dirname(output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    plt = _require_matplotlib()
    fig.savefig(output, dpi=dpi)
    plt.close(fig)

    return output


def plot_drift_bytes(old, new, columns=None, ignore_columns=None,
                      bins=10, style=None, max_cols_per_row=3,
                      figsize_per_plot=(4.5, 3.5), title=None, dpi=120):
    """
    Same chart as plot_drift(), but returns PNG bytes in memory instead of
    saving to a file. Used to embed a chart directly into an HTML report
    (to_html(embed_chart=...)) without creating a separate image file the
    user has to keep track of alongside the report.

    Returns:
        bytes (PNG image data), or None if there were no plottable columns.
        Returns None rather than raising in that no-columns case, since
        embedding is meant to be a best-effort addition to a report rather
        than something that should fail the whole compare() call — a
        missing chart in an HTML report is a much smaller problem than a
        missing report entirely.

    Raises:
        ImportError: matplotlib is not installed.
    """
    import io

    try:
        fig = _build_figure(
            old, new, columns=columns, ignore_columns=ignore_columns,
            bins=bins, style=style, max_cols_per_row=max_cols_per_row,
            figsize_per_plot=figsize_per_plot, title=title,
        )
    except ValueError:
        return None

    plt = _require_matplotlib()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
