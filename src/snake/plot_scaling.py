"""Plot the scaling benchmark: pyreadstat chunking vs DuckDB.

Reads the long-format CSV written by `src/snake/bench_scaling.py`:

    language,task,tool,format,size,timing,branch

Rows are tagged with the `duckdb-read-stat` branch; every series is split per
branch (different marker) and labelled with it. `--branch` restricts the plots
to one branch. The `parallel-proto` branch is excluded: this benchmark only
covers the pull-reader extension.

When the CSV mixes formats (e.g. row-compressed .sav and .sas7bdat), each
format is drawn as a separate line. The script writes two plots: the absolute
read time and the average time per row vs dataset size, both on linear axes,
with 95% confidence intervals on every point (mean ± t(0.975, n-1)·SEM).
No runs are dropped. The printed summary also reports the fitted log-log slope
of the total time (near 1 = linear scaling, near 2 = quadratic). Time per row is
independent of the chunk size.

Usage:
    uv run src/snake/plot_scaling.py
    uv run src/snake/plot_scaling.py results/bench_scaling.csv -o results/figs
    uv run src/snake/plot_scaling.py --format sas7bdat
"""

# /// script
# dependencies = [
#   "matplotlib",
#   "numpy",
#   "pandas",
# ]
# ///

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.transforms import ScaledTranslation

COLUMNS = ["language", "task", "tool", "format", "size", "timing", "branch"]
# The scaling benchmark is only meaningful for the pull-reader extension; the
# parallel-proto branch is excluded from these plots.
EXCLUDED_BRANCHES = {"parallel-proto"}
TOOL_ORDER = ["pyreadstat_chunked", "duckdb"]
TOOL_COLORS = {
    "pyreadstat_chunked": "tab:cyan",
    "duckdb": "tab:orange",
}
FORMAT_ORDER = ["sav_row_compress", "sas7bdat"]
FORMAT_LINESTYLES = ["-", "--", ":"]
# Branches are separated by line marker (and named in the legend when the CSV
# holds more than one).
BRANCH_MARKERS = {
    "pull-reader-proto": "o",
    "parallel-proto": "s",
    "develop": "^",
}
FALLBACK_BRANCH_MARKERS = ["D", "v", "P", "X"]
SIZE_MULTIPLIERS = {"k": 1_000, "m": 1_000_000}


def parse_rows(label: str) -> int:
    """Convert a size label such as '100k' or '50m' to a number of rows."""
    text = str(label).strip().lower()
    if text and text[-1] in SIZE_MULTIPLIERS:
        return int(float(text[:-1]) * SIZE_MULTIPLIERS[text[-1]])
    return int(float(text))


def load_results(path: Path, branch: str | None = None) -> pd.DataFrame:
    """Read the long-format scaling CSV (optionally filtered to `branch`)."""
    df = pd.read_csv(path, header=None, names=COLUMNS)
    # Tolerate a header row in case the file format gains one later.
    df = df[df["language"] != COLUMNS[0]].copy()
    if df[COLUMNS].isna().any().any():
        raise SystemExit(
            f"{path} does not have the expected {len(COLUMNS)} columns "
            f"({','.join(COLUMNS)})"
        )
    df["timing"] = pd.to_numeric(df["timing"])
    if branch is not None:
        available = ", ".join(sorted(df["branch"].unique()))
        df = df[df["branch"] == branch].copy()
        if df.empty:
            raise SystemExit(
                f"no rows for branch {branch!r} in {path}; available: {available}"
            )
    try:
        df["rows"] = df["size"].map(parse_rows)
    except ValueError as exc:
        raise SystemExit(f"cannot parse size labels in {path}: {exc}") from exc
    return df


def _sem(sd: float, runs: int) -> float:
    """Standard error of a mean; NaN when a single run gives no spread."""
    if runs < 2 or not math.isfinite(sd):
        return math.nan
    return sd / math.sqrt(runs)


# Two-sided 95% Student-t quantiles for df = 1..30; the normal value (1.96) is
# used above that. Kept local so this script stays dependency-free (no scipy).
T975 = [
    12.706205, 4.302653, 3.182446, 2.776445, 2.570582,
    2.446912, 2.364624, 2.306004, 2.262157, 2.228139,
    2.200985, 2.178813, 2.160369, 2.144787, 2.131450,
    2.119905, 2.109816, 2.100922, 2.093024, 2.085963,
    2.079614, 2.073873, 2.068658, 2.063899, 2.059539,
    2.055529, 2.051831, 2.048407, 2.045230, 2.042272,
]


def _t975(df: int) -> float:
    """Two-sided 95% t quantile; NaN below 1 df, normal above 30 df."""
    if df < 1:
        return math.nan
    return T975[df - 1] if df <= len(T975) else 1.96


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """Mean timing, its 95% CI, and per-row time per tool, branch, and size."""
    stats = (
        df.groupby(["tool", "format", "branch", "rows"], as_index=False)["timing"]
        .agg(runs="count", mean="mean", sd="std")
        .sort_values(["format", "branch", "tool", "rows"])
    )
    stats["sem"] = [_sem(sd, runs) for sd, runs in zip(stats["sd"], stats["runs"])]
    stats["ci95"] = [
        _t975(runs - 1) * sem if math.isfinite(sem) else math.nan
        for sem, runs in zip(stats["sem"], stats["runs"])
    ]
    stats["time_per_row"] = stats["mean"] / stats["rows"]
    stats["ci95_per_row"] = stats["ci95"] / stats["rows"]
    stats["rows_per_s"] = stats["rows"] / stats["mean"]
    return stats


def tools_in_order(df: pd.DataFrame) -> list[str]:
    present = set(df["tool"])
    known = [tool for tool in TOOL_ORDER if tool in present]
    return known + sorted(present - set(known))


def formats_in_order(df: pd.DataFrame) -> list[str]:
    present = set(df["format"])
    known = [fmt for fmt in FORMAT_ORDER if fmt in present]
    return known + sorted(present - set(known))


def series_in_order(stats: pd.DataFrame):
    """Yield (label, color, linestyle, marker, subset) per tool/format/branch.

    The label always names the file format, and adds the extension branch when
    the CSV holds more than one; the marker also distinguishes the branches.
    """
    branches = sorted(stats["branch"].unique())
    multi_branch = len(branches) > 1
    fallback = iter(FALLBACK_BRANCH_MARKERS)
    markers = {
        branch: BRANCH_MARKERS.get(branch) or next(fallback, "o")
        for branch in branches
    }
    for fmt_index, fmt in enumerate(formats_in_order(stats)):
        fmt_stats = stats[stats["format"] == fmt]
        for branch in branches:
            branch_stats = fmt_stats[fmt_stats["branch"] == branch]
            for tool in tools_in_order(branch_stats):
                label = f"{tool} ({fmt})"
                if multi_branch:
                    label += f" [{branch}]"
                yield (
                    label,
                    TOOL_COLORS.get(tool, "tab:gray"),
                    FORMAT_LINESTYLES[fmt_index % len(FORMAT_LINESTYLES)],
                    markers[branch],
                    branch_stats[branch_stats["tool"] == tool].sort_values("rows"),
                )


def format_rows(n_rows: int) -> str:
    """Compact tick label such as 100k or 50m."""
    if n_rows % 1_000_000 == 0:
        return f"{n_rows // 1_000_000}m"
    if n_rows % 1_000 == 0:
        return f"{n_rows // 1_000}k"
    return f"{n_rows:,}"


def style_size_axis(fig, ax, rows: list[int]) -> None:
    """Compact, staggered x tick labels for a linear rows axis."""
    ax.set_xticks(rows)
    ax.set_xticklabels([format_rows(n) for n in rows])
    # On a linear axis, labels for nearby sizes (e.g. 100k and 1m) overlap;
    # stagger those close labels vertically.
    stagger = False
    previous = None
    for label, n_rows in zip(ax.get_xticklabels(), rows):
        close = previous is not None and (n_rows - previous) / max(rows) < 0.05
        stagger = not stagger if close else False
        if stagger:
            label.set_transform(
                label.get_transform()
                + ScaledTranslation(0, -0.12, fig.dpi_scale_trans)
            )
        previous = n_rows
    ax.set_xlabel("rows")


def plot_time(stats: pd.DataFrame, out: Path) -> None:
    """Absolute read time vs dataset size on linear axes."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for label, color, linestyle, marker, sub in series_in_order(stats):
        ax.plot(
            sub["rows"],
            sub["mean"],
            marker=marker,
            linewidth=1.5,
            linestyle=linestyle,
            color=color,
            label=label,
        )
        ok = np.isfinite(sub["ci95"])
        if ok.any():
            ax.errorbar(
                sub.loc[ok, "rows"],
                sub.loc[ok, "mean"],
                yerr=sub.loc[ok, "ci95"],
                fmt="none",
                ecolor=color,
                elinewidth=1.0,
                capsize=3,
            )

    style_size_axis(fig, ax, sorted(stats["rows"].unique()))
    ax.set_ylabel("time [s]")
    ax.set_title("Scaling: absolute read time vs dataset size (mean, 95% CI)")
    ax.grid(alpha=0.3)
    ax.legend(title="tool (file format) [branch]", fontsize="small")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_time_per_row(stats: pd.DataFrame, out: Path) -> None:
    """Average time per row vs dataset size on linear axes."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for label, color, linestyle, marker, sub in series_in_order(stats):
        ax.plot(
            sub["rows"],
            sub["time_per_row"] * 1e6,
            marker=marker,
            linewidth=1.5,
            linestyle=linestyle,
            color=color,
            label=label,
        )
        ok = np.isfinite(sub["ci95_per_row"])
        if ok.any():
            ax.errorbar(
                sub.loc[ok, "rows"],
                sub.loc[ok, "time_per_row"] * 1e6,
                yerr=sub.loc[ok, "ci95_per_row"] * 1e6,
                fmt="none",
                ecolor=color,
                elinewidth=1.0,
                capsize=3,
            )

    style_size_axis(fig, ax, sorted(stats["rows"].unique()))
    ax.set_ylabel("average time per row [µs]")
    ax.set_title("Scaling: average time per row vs dataset size (mean, 95% CI)")
    ax.grid(alpha=0.3)
    ax.legend(title="tool (file format) [branch]", fontsize="small")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def print_summary(stats: pd.DataFrame) -> None:
    table = stats.assign(
        ci95_s=stats["ci95"].map(lambda v: f"{v:.4f}"),
        throughput=stats["rows_per_s"].map(lambda v: f"{v:,.0f} rows/s"),
        per_row=stats["time_per_row"].map(lambda v: f"{v * 1e6:.3f} µs/row"),
    )[
        [
            "tool",
            "format",
            "branch",
            "rows",
            "runs",
            "mean",
            "ci95_s",
            "per_row",
            "throughput",
        ]
    ]
    print(f"\n{table.to_string(index=False)}\n")

    print("log-log slopes (fit over all sizes):")
    for label, _color, _linestyle, _marker, sub in series_in_order(stats):
        sub = sub.sort_values("rows")
        if len(sub) < 2:
            print(f"  {label}: need at least two sizes")
            continue
        slope = np.polyfit(np.log(sub["rows"]), np.log(sub["mean"]), 1)[0]
        print(f"  {label}: {slope:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv", nargs="?", default="results/bench_scaling.csv", type=Path
    )
    parser.add_argument("-o", "--outdir", default="results/figs", type=Path)
    parser.add_argument(
        "--format",
        dest="file_format",
        choices=FORMAT_ORDER,
        default=None,
        help="only plot this file format",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="only plot this extension branch (default: all branches)",
    )
    args = parser.parse_args()

    df = load_results(args.csv, args.branch)
    excluded = df["branch"].isin(EXCLUDED_BRANCHES)
    if excluded.any():
        print(
            "note: excluding branches "
            f"{', '.join(sorted(df.loc[excluded, 'branch'].unique()))}"
        )
        df = df[~excluded].copy()
    if df.empty:
        raise SystemExit(
            "no scaling rows left after excluding "
            f"{', '.join(sorted(EXCLUDED_BRANCHES))}"
        )
    if args.file_format is not None:
        df = df[df["format"] == args.file_format].copy()
        if df.empty:
            raise SystemExit(
                f"no scaling rows match format {args.file_format!r}"
            )
    stats = summarise(df)
    args.outdir.mkdir(parents=True, exist_ok=True)

    print_summary(stats)
    plot_time(stats, args.outdir / "scaling_time.png")
    plot_time_per_row(stats, args.outdir / "scaling_time_per_row.png")
    print(f"wrote plots to {args.outdir}/")


if __name__ == "__main__":
    main()
