"""Create row-compressed SPSS files of increasing size for scaling benchmarks.

The files have a minimal numeric schema (person_id, wage) so the largest
dataset (50M rows) stays within a reasonable memory/disk budget. They are
written with `row_compress=True`, i.e. they use row compression.

Usage:
    uv run src/snake/create_scaling_stat_file.py
    uv run src/snake/create_scaling_stat_file.py --sizes 100k 1m
    uv run src/snake/create_scaling_stat_file.py --sizes 50m --force
"""

# /// script
# dependencies = [
#     "numpy",
#     "pandas",
#     "pyreadstat",
# ]
# ///

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

# Label -> number of rows. Keep this in sync with src/snake/bench_scaling.py.
SIZES: dict[str, int] = {
    "100k": 100_000,
    "1m": 1_000_000,
    "10m": 10_000_000,
    "50m": 50_000_000,
}
# 50m is opt-in: it is slow to generate and benchmark.
DEFAULT_SIZES = ["100k", "1m", "10m"]

DEFAULT_OUTDIR = Path("data/scaling")


def file_name(label: str) -> str:
    """Name of the row-compressed .sav file for a size label."""
    return f"test_{label}.sav_row_compress"


def build_data(n_rows: int, seed: int) -> pd.DataFrame:
    """Build a small numeric dataframe with `n_rows` rows."""
    rng = np.random.default_rng(seed)
    # pandas wraps the existing numpy arrays, so this avoids an extra copy.
    return pd.DataFrame(
        {
            "person_id": rng.integers(0, 2**31 - 1, size=n_rows, dtype=np.int32),
            "wage": rng.random(n_rows),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        nargs="+",
        choices=list(SIZES),
        default=DEFAULT_SIZES,
        help=f"size labels to generate (default: {' '.join(DEFAULT_SIZES)})",
    )
    parser.add_argument(
        "--outdir", type=Path, default=DEFAULT_OUTDIR, help="output directory"
    )
    parser.add_argument("--seed", type=int, default=1234, help="random seed")
    parser.add_argument(
        "--force", action="store_true", help="overwrite existing files"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args.outdir.mkdir(parents=True, exist_ok=True)

    for label in args.sizes:
        n_rows = SIZES[label]
        path = args.outdir / file_name(label)
        if path.exists() and not args.force:
            logging.info("%s already exists, skipping (use --force)", path)
            continue

        logging.info("building %s rows ...", f"{n_rows:,}")
        df = build_data(n_rows, args.seed)
        pyreadstat.write_sav(df, str(path), row_compress=True)
        size_gib = path.stat().st_size / 2**30
        logging.info("wrote %s (%.2f GiB, %s rows)", path, size_gib, f"{n_rows:,}")
        del df


if __name__ == "__main__":
    main()
