"""Plot benchmark results: DuckDB vs. the native bindings (pyreadstat, haven).

The CSV written by `src/bench/run.sh` is append-only and has no run column, so
consecutive benchmark runs are told apart by the start of each run's Python
block (`python, read_all, pyreadstat`). Rows are also tagged with the
`duckdb-read-stat` branch; all branches are plotted by default, and `--branch`
restricts the figure to one of them.

`mean_timing.png` has three panels labelled by task: `python: read`, `R: read`,
and `python: read + write parquet`. `duckdb_speedup.png` uses the same panels
but plots the ratio native/DuckDB per branch (above 1 means DuckDB is faster).
Every read covers the whole file (there is no row limit). DuckDB bars are split per
extension branch (one color per branch); native clients (pyreadstat, haven) are
pooled across branches into a single bar. Error bars are 95% confidence
intervals (mean ± t(0.975, n-1)·SEM, SEM = sd/sqrt(runs)), drawn only for bars
that average more than one run; the speedup propagates the SEMs of the two means
in quadrature (treated as independent samples) with t on min(n)-1 df, i.e. wider
than the paired Welch interval. No resampling and no runs dropped. A single
legend at the bottom maps each color to its tool and, for DuckDB, the extension
branch; a footnote names the branches behind the short legend labels
(`pull reader`, `+ parallel`).

The `read_all` and `read_all_chunked` tasks are currently disabled; the
chunked-read remapping below is kept so they can be re-enabled. When
`read_all_chunked` is active it is plotted as a `pyreadstat_chunked` bar in the
`read_all` group.

Usage:
    uv run src/snake/plot_bench.py                       # results/bench.csv
    uv run src/snake/plot_bench.py other/bench.csv -o figs
    uv run src/snake/plot_bench.py --format dta
"""

# /// script
# dependencies = [
#   "pandas",
#   "matplotlib",
# ]
# ///

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

COLUMNS = ["language", "task", "tool", "format", "size", "timing", "branch"]
# Keep in sync with the first task written by src/snake/bench.py: it marks the
# start of each python block, i.e. of each benchmark run.
RUN_START = {"language": "python", "task": "read_all", "tool": "pyreadstat"}
SIZES = ["cbs"]
FORMATS = ["dta", "sav", "sav_row_compress"]

# Human-readable task names for axis labels.
TASK_LABELS = {
    "read_all": "read all rows",
    "read_all_parquet": "read all rows\n+ write parquet",
    "read_all_chunked": "read all rows (chunked)",
}
READ_TASKS = ["read_all", "read_all_chunked"]
PARQUET_TASKS = ["read_all_parquet"]

# The chunked pyreadstat read is plotted as another variant of a full read,
# next to the default pyreadstat and DuckDB bars.
CHUNKED_TASK = "read_all_chunked"
CHUNKED_TOOL = "pyreadstat_chunked"

# DuckDB clients: the same extension, reached through python, R, or the CLI.
DUCKDB_CLIENTS = {
    "python": "duckdb (python)",
    "R": "duckdb (R)",
    "sql": "duckdb (SQL)",
}

# Short branch names for the legend; DuckDB bar colors follow the branch.
BRANCH_LABELS = {
    "pull-reader-proto": "pull reader",
    "parallel-proto": "+ parallel",
    "develop": "develop",
}
DUCKDB_BRANCH_COLORS = {
    "pull-reader-proto": "tab:orange",
    "parallel-proto": "tab:purple",
    "develop": "tab:brown",
}
FALLBACK_BRANCH_COLORS = ["tab:olive", "tab:pink", "tab:gray", "tab:cyan"]
# Draw order: the native clients first, then DuckDB (pull reader before
# "+ parallel").
NATIVE_ORDER = ["pyreadstat", CHUNKED_TOOL, "haven"]
BRANCH_ORDER = ["pull-reader-proto", "parallel-proto", "develop"]
CLIENT_COLORS = {
    "pyreadstat": "tab:blue",
    CHUNKED_TOOL: "tab:cyan",
    "haven": "tab:green",
}

# Panels of mean_timing.png: (title, clients, tasks).
# Speedup panels: (title, clients, tasks, native tool to compare against).
SPEEDUP_PANELS = [
    ("python: read", ["pyreadstat", "duckdb (python)"], READ_TASKS, "pyreadstat"),
    ("R: read", ["haven", "duckdb (R)"], READ_TASKS, "haven"),
    (
        "python: read + write parquet",
        ["pyreadstat", "duckdb (python)"],
        PARQUET_TASKS,
        "pyreadstat",
    ),
]

MEAN_PANELS = [
    ("python: read", ["pyreadstat", CHUNKED_TOOL, "duckdb (python)"], READ_TASKS),
    ("R: read", ["haven", "duckdb (R)"], READ_TASKS),
    (
        "python: read + write parquet",
        ["pyreadstat", "duckdb (python)"],
        PARQUET_TASKS,
    ),
]


def load_results(path: Path, branch: str | None = None) -> pd.DataFrame:
    """Read the long-format CSV and tag every row with its benchmark run."""
    df = pd.read_csv(path, header=None, names=COLUMNS)
    # Tolerate a header row in case the file format gains one later.
    df = df[df["language"] != COLUMNS[0]].copy()
    if df[COLUMNS].isna().any().any():
        raise SystemExit(
            f"{path} does not have the expected {len(COLUMNS)} columns "
            f"({','.join(COLUMNS)}); remove results from older benchmark versions"
        )
    df["timing"] = pd.to_numeric(df["timing"])
    if branch is not None:
        available = ", ".join(sorted(df["branch"].unique()))
        df = df[df["branch"] == branch].copy()
        if df.empty:
            raise SystemExit(
                f"no rows for branch {branch!r} in {path}; available: {available}"
            )

    is_start = True
    for col, value in RUN_START.items():
        is_start = is_start & df[col].eq(value)
    df["run"] = is_start.cumsum()
    # Rows before the first run marker cannot be attributed to a run.
    n_dropped = int((df["run"] == 0).sum())
    if n_dropped:
        print(f"warning: dropping {n_dropped} row(s) before the first run marker")
    df = df[df["run"] > 0].copy()
    df["run"] = df["run"].astype(int)
    df["size"] = pd.Categorical(df["size"], categories=SIZES, ordered=True)
    df["format"] = pd.Categorical(df["format"], categories=FORMATS, ordered=True)

    # Plot the chunked read as a separate tool in the read_all group instead
    # of as its own task.
    is_chunked = df["task"] == CHUNKED_TASK
    df.loc[is_chunked, "task"] = "read_all"
    df.loc[is_chunked, "tool"] = CHUNKED_TOOL
    return df


def filter_results(
    df: pd.DataFrame, size: str | None, file_format: str | None
) -> pd.DataFrame:
    if size is not None:
        df = df[df["size"] == size]
    if file_format is not None:
        df = df[df["format"] == file_format]
    if df.empty:
        raise SystemExit("no benchmark rows match the selected size/format")
    return df.copy()


def duckdb_label(branch: str) -> str:
    """Legend label of a DuckDB bar for an extension branch."""
    return f"duckdb ({BRANCH_LABELS.get(branch, branch)})"


def add_client_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add `client` (panel selection) and `column` (bar identity / legend label).

    DuckDB bars are keyed by extension branch, so both branches show up side by
    side with their own color. Native clients (pyreadstat, haven, ...) do not
    depend on the extension, so their runs are pooled across branches into a
    single bar.
    """
    df = df.copy()
    df["branch"] = df["branch"].astype(str)
    df["client"] = [
        DUCKDB_CLIENTS.get(lang, tool) if tool == "duckdb" else tool
        for lang, tool in zip(df["language"].astype(str), df["tool"])
    ]
    df["column"] = [
        duckdb_label(branch) if client.startswith("duckdb") else client
        for client, branch in zip(df["client"], df["branch"])
    ]
    return df


def ordered_branches(branches) -> list[str]:
    """Known branches in drawing order, then any others alphabetically."""
    known = [branch for branch in BRANCH_ORDER if branch in set(branches)]
    return known + sorted(set(branches) - set(known))


def branch_footnote(df: pd.DataFrame) -> str:
    """Footnote mapping the short legend names back to extension branches."""
    pairs = [
        f"{BRANCH_LABELS.get(branch, branch)} = {branch}"
        for branch in ordered_branches(df["branch"].unique())
    ]
    if len(pairs) == 1:
        return f"duckdb extension branch: {pairs[0]}"
    return f"duckdb extension branches: {'; '.join(pairs)}"


def ordered_columns(df: pd.DataFrame) -> list[str]:
    """Bar order used in every panel and in the shared legend."""
    present = set(df["column"])
    known = NATIVE_ORDER + [
        duckdb_label(branch) for branch in ordered_branches(df["branch"].unique())
    ]
    columns = [column for column in known if column in present]
    return columns + sorted(present - set(columns))


def column_colors(df: pd.DataFrame) -> dict[str, str]:
    """Color per bar identity: native tools fixed, DuckDB by branch."""
    present = set(df["column"])
    colors = {column: CLIENT_COLORS[column] for column in NATIVE_ORDER if column in present}
    fallback = iter(FALLBACK_BRANCH_COLORS)
    for branch in ordered_branches(df["branch"].unique()):
        color = DUCKDB_BRANCH_COLORS.get(branch) or next(fallback, "tab:gray")
        colors[duckdb_label(branch)] = color
    for column in present - set(colors):
        colors[column] = "tab:gray"
    return colors


def _sem(sd: float, runs: int) -> float:
    """Standard error of a mean; NaN when a single run gives no spread."""
    if runs < 2 or not math.isfinite(sd):
        return math.nan
    return sd / math.sqrt(runs)


# Two-sided 95% Student-t quantiles for df = 1..30; the normal value (1.96) is
# used above that. Keeps the script free of a scipy dependency.
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


def _ci95(sem: float, df: int) -> float:
    """Half-width of a 95% confidence interval from a standard error."""
    if not math.isfinite(sem):
        return math.nan
    return _t975(df) * sem


def _panel_stats(df: pd.DataFrame, clients: list[str], tasks: list[str]) -> pd.DataFrame | None:
    """Mean/95% CI/run-count per file format, task, and bar column."""
    sub = df[df["client"].isin(clients) & df["task"].isin(tasks)]
    if sub.empty:
        return None
    group_cols = ["size", "format", "task"]
    stats = (
        sub.groupby(group_cols + ["column"], observed=True)["timing"]
        .agg(runs="count", mean="mean", sd="std")
        .reset_index()
    )
    stats["sem"] = [_sem(sd, runs) for sd, runs in zip(stats["sd"], stats["runs"])]
    stats["ci95"] = [
        _ci95(sem, runs - 1) for sem, runs in zip(stats["sem"], stats["runs"])
    ]
    labels = stats["size"].astype(str) + "/" + stats["format"].astype(str)
    if sub["task"].nunique() > 1:
        labels = labels + "\n" + stats["task"].map(
            lambda task: TASK_LABELS.get(task, task)
        )
    stats["group"] = labels
    return stats


def _draw_panel(
    ax, stats: pd.DataFrame, columns: list[str], colors: dict[str, str]
) -> None:
    groups = list(dict.fromkeys(stats["group"]))
    columns = [column for column in columns if column in set(stats["column"])]
    width = 0.8 / max(len(columns), 1)
    top = 0.0
    for ci, column in enumerate(columns):
        sub = stats[stats["column"] == column].set_index("group")
        xs, heights, errors, runs = [], [], [], []
        for gi, group in enumerate(groups):
            if group not in sub.index:
                continue
            row = sub.loc[group]
            n_runs = int(row["runs"])
            xs.append(gi + (ci - (len(columns) - 1) / 2) * width)
            heights.append(float(row["mean"]))
            runs.append(n_runs)
            # No error bar when a bar is a single run (no CI is defined).
            ci95 = float(row["ci95"])
            errors.append(ci95 if math.isfinite(ci95) else 0.0)
        ax.bar(
            xs,
            heights,
            width=width,
            color=colors[column],
            edgecolor="black",
            linewidth=0.4,
        )
        with_errors = [i for i, n in enumerate(runs) if n > 1 and errors[i] > 0]
        if with_errors:
            ax.errorbar(
                [xs[i] for i in with_errors],
                [heights[i] for i in with_errors],
                yerr=[errors[i] for i in with_errors],
                fmt="none",
                ecolor="black",
                capsize=3,
            )
        top = max([top] + [height + error for height, error in zip(heights, errors)])
    ax.set_xticks(range(len(groups)))
    long_labels = any(len(group) > 10 for group in groups)
    ax.set_xticklabels(
        groups,
        fontsize="small",
        rotation=20 if long_labels else 0,
        ha="right" if long_labels else "center",
    )
    ax.set_ylabel("time [s]")
    ax.set_ylim(0, top * 1.1 if top > 0 else 1)
    ax.grid(axis="y", alpha=0.3)


def plot_means(df: pd.DataFrame, out: Path) -> None:
    """Mean timing per panel and tool, with one shared legend."""
    df = add_client_columns(df)
    columns = ordered_columns(df)
    colors = column_colors(df)

    panels = []
    for title, clients, tasks in MEAN_PANELS:
        present = [client for client in clients if client in set(df["client"])]
        stats = _panel_stats(df, present, tasks)
        if stats is not None:
            panels.append((title, stats))
    if not panels:
        print("warning: no rows match the mean-timing panels")
        return

    fig, axes = plt.subplots(
        1, len(panels), figsize=(4.6 * len(panels), 4.4), squeeze=False
    )
    for ax, (title, stats) in zip(axes[0], panels):
        _draw_panel(ax, stats, columns, colors)
        ax.set_title(title)

    fig.suptitle("Benchmark timing by tool (mean, 95% CI)")
    _add_shared_legend(fig, columns, colors, df)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _speedup_stats(
    stats: pd.DataFrame, native: str, duckdb_columns: list[str]
) -> pd.DataFrame:
    """Ratio of means native/duckdb per bar group, plus its 95% confidence
    interval."""
    native_stats = stats[stats["column"] == native].set_index("group")
    rows = []
    for column in duckdb_columns:
        duckdb_stats = stats[stats["column"] == column].set_index("group")
        for group in native_stats.index:
            if group not in duckdb_stats.index:
                continue
            native_row = native_stats.loc[group]
            duckdb_row = duckdb_stats.loc[group]
            ratio = native_row["mean"] / duckdb_row["mean"]
            # Two independent means: relative standard errors add in quadrature.
            sem = math.nan
            if math.isfinite(native_row["sem"]) and math.isfinite(duckdb_row["sem"]):
                relative = (native_row["sem"] / native_row["mean"]) ** 2 + (
                    duckdb_row["sem"] / duckdb_row["mean"]
                ) ** 2
                sem = ratio * math.sqrt(relative)
            # min(n)-1 df is the conservative choice: the Welch-Satterthwaite df
            # of two independent means is never smaller, so t (and the CI) is
            # never narrower.
            df = min(int(native_row["runs"]), int(duckdb_row["runs"])) - 1
            rows.append(
                {
                    "group": group,
                    "column": column,
                    "ratio": ratio,
                    "sem": sem,
                    "ci95": _ci95(sem, df),
                }
            )
    return pd.DataFrame(rows)


def plot_speedup(df: pd.DataFrame, out: Path) -> None:
    """DuckDB speedup over the native reader, one panel per task (like
    mean_timing.png). A value above 1 means DuckDB is faster."""
    df = add_client_columns(df)
    colors = column_colors(df)
    all_columns = ordered_columns(df)
    duckdb_columns = [column for column in all_columns if column.startswith("duckdb")]

    panels = []
    for title, clients, tasks, native in SPEEDUP_PANELS:
        present = [client for client in clients if client in set(df["client"])]
        stats = _panel_stats(df, present, tasks)
        if stats is None:
            continue
        ratios = _speedup_stats(stats, native, duckdb_columns)
        if not ratios.empty:
            panels.append((title, ratios))
    if not panels:
        print("warning: no rows match the speedup panels")
        return

    fig, axes = plt.subplots(
        1, len(panels), figsize=(4.6 * len(panels), 4.4), squeeze=False
    )
    top = 0.0
    for ax, (title, ratios) in zip(axes[0], panels):
        groups = list(dict.fromkeys(ratios["group"]))
        columns = [column for column in duckdb_columns if column in set(ratios["column"])]
        width = 0.8 / max(len(columns), 1)
        for ci, column in enumerate(columns):
            sub = ratios[ratios["column"] == column].set_index("group")
            xs, heights, errors = [], [], []
            for gi, group in enumerate(groups):
                if group not in sub.index:
                    continue
                row = sub.loc[group]
                xs.append(gi + (ci - (len(columns) - 1) / 2) * width)
                heights.append(float(row["ratio"]))
                ci95 = float(row["ci95"])
                errors.append(ci95 if math.isfinite(ci95) else math.nan)
            ax.bar(
                xs,
                heights,
                width=width,
                color=colors[column],
                edgecolor="black",
                linewidth=0.4,
            )
            with_errors = [i for i, error in enumerate(errors) if error > 0]
            if with_errors:
                ax.errorbar(
                    [xs[i] for i in with_errors],
                    [heights[i] for i in with_errors],
                    yerr=[errors[i] for i in with_errors],
                    fmt="none",
                    ecolor="black",
                    capsize=3,
                )
            top = max(
                [top]
                + [
                    height + error
                    for height, error in zip(heights, errors)
                    if math.isfinite(error)
                ]
            )
        ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
        ax.set_xticks(range(len(groups)))
        long_labels = any(len(group) > 10 for group in groups)
        ax.set_xticklabels(
            groups,
            fontsize="small",
            rotation=20 if long_labels else 0,
            ha="right" if long_labels else "center",
        )
        ax.set_ylabel("speedup: native / DuckDB")
        ax.set_ylim(0, max(top, 1.0) * 1.1)
        ax.grid(axis="y", alpha=0.3)
        ax.set_title(title)

    fig.suptitle(
        "DuckDB speedup over the native readers "
        "(ratio of means, 95% CI; >1 = DuckDB faster)"
    )
    _add_shared_legend(fig, duckdb_columns, colors, df)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _add_shared_legend(
    fig, columns: list[str], colors: dict[str, str], df: pd.DataFrame
) -> None:
    """Shared legend plus the branch footnote, in a band below the panels."""
    handles = [
        Patch(facecolor=colors[column], edgecolor="black", label=column)
        for column in columns
    ]
    # Reserve a band at the bottom for the legend and the footnote.
    fig.tight_layout(rect=(0, 0.16, 1, 1))
    fig.legend(
        handles=handles,
        loc="center",
        bbox_to_anchor=(0.5, 0.09),
        ncol=min(len(handles), 4),
        frameon=False,
        title="tool (extension branch)",
    )
    fig.text(
        0.5,
        0.02,
        branch_footnote(df),
        ha="center",
        va="bottom",
        fontsize=8,
        color="dimgray",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", default="results/bench.csv", type=Path)
    parser.add_argument("-o", "--outdir", default="results/figs", type=Path)
    parser.add_argument(
        "--size", choices=SIZES, default=None, help="only plot this dataset size"
    )
    parser.add_argument(
        "--format", dest="file_format", choices=FORMATS, default=None,
        help="only plot this file format",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="only plot this extension branch (default: all branches)",
    )
    args = parser.parse_args()

    df = filter_results(
        load_results(args.csv, args.branch), args.size, args.file_format
    )
    args.outdir.mkdir(parents=True, exist_ok=True)

    summary_keys = ["language", "size", "format", "task", "tool"]
    if df["branch"].astype(str).nunique() > 1:
        # Keep branches apart when the CSV mixes extension versions.
        summary_keys.insert(1, "branch")
    summary = (
        df.groupby(
            summary_keys, observed=True
        )["timing"]
        .agg(
            runs="count",
            mean="mean",
            sd="std",
            sem=lambda s: s.std() / math.sqrt(len(s)),
            ci95=lambda s: _ci95(s.std() / math.sqrt(len(s)), len(s) - 1),
            median="median",
        )
        .round(4)
    )
    print(f"\n{summary}\n")

    plot_means(df, args.outdir / "mean_timing.png")
    plot_speedup(df, args.outdir / "duckdb_speedup.png")
    print(f"wrote plots to {args.outdir}/")


if __name__ == "__main__":
    main()
