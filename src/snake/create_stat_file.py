# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy",
#     "polars",
#     "pyreadstat",
# ]
# ///
"""Create a test SPSS (.sav) or Stata (.dta) file.

The generated table has 30 numeric columns, all fully populated: no missing
values, no user-missing ranges, so pyreadstat and DuckDB read the same data.

Usage:
    uv run src/snake/create_stat_file.py [-o OUTPUT] [--format {dta,sav,sav_row_compress}] [--seed SEED]
    uv run src/snake/create_stat_file.py --dry-run [--format {dta,sav,sav_row_compress}]
"""

import argparse
from pathlib import Path

import numpy as np
import polars as pl
import pyreadstat

# Number of observations written by a real run. `--dry-run` only writes
# DRY_RUN_N_OBS rows so the whole pipeline can be tested quickly.
N_OBS = 1_000_000
DRY_RUN_N_OBS = 10

# The table has 30 numeric columns. `person_id`, `wage`, and `sector` are
# hand-written below, the `num_XX` columns are generated.
N_COLUMNS = 30
COLUMNS = [
    "person_id",
    "wage",
    "sector",
    *(f"num_{i:02d}" for i in range(1, 28)),
]
assert len(COLUMNS) == N_COLUMNS, f"expected {N_COLUMNS} columns"

COLUMN_LABELS: dict[str, str] = {
    "person_id": "Person identifier",
    "wage": "Hourly wage",
    "sector": "Economic sector",
    **{f"num_{i:02d}": f"Numeric column {i}" for i in range(1, 28)},
}

VARIABLE_VALUE_LABELS: dict[str, dict[float, str]] = {
    "sector": {1.0: "sector a", 2.0: "sector b", 3.0: "sector c"},
}


def build_data(n: int, seed: int) -> pl.DataFrame:
    """Build the test dataframe; every column is fully populated."""
    rng = np.random.default_rng(seed)
    data: dict[str, np.ndarray] = {
        # person IDs are coded as int32 so they also fit in a .dta file
        "person_id": rng.integers(1, 1_000_000_000, size=n, dtype=np.int32),
        "wage": rng.random(size=n),
        "sector": rng.choice([1.0, 2.0, 3.0], size=n),
    }
    # remaining numeric columns
    for i in range(1, 28):
        data[f"num_{i:02d}"] = rng.random(size=n)

    assert list(data) == COLUMNS, "generated columns do not match COLUMNS"
    return pl.DataFrame(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=None, help="output path (default: file_in.<format>, or file_dry_run.<format> with --dry-run)")
    parser.add_argument("--format", choices=["dta", "sav", "sav_row_compress"], default="sav", help="output file format")
    parser.add_argument("--seed", type=int, default=1234, help="random seed")
    parser.add_argument("--dry-run", action="store_true", help=f"only write {DRY_RUN_N_OBS} rows as a quick test")
    args = parser.parse_args()

    prefix = "file_dry_run" if args.dry_run else "file_in"
    output = args.output or Path(f"{prefix}.{args.format}")
    n_obs = DRY_RUN_N_OBS if args.dry_run else N_OBS
    data = build_data(n_obs, args.seed)
    match args.format:
        case "dta":
            pyreadstat.write_dta(
                data,
                str(output),
                column_labels=COLUMN_LABELS,
                variable_value_labels=VARIABLE_VALUE_LABELS,
            )
        case "sav": # no compression
            pyreadstat.write_sav(
                data,
                str(output),
                column_labels=COLUMN_LABELS,
                variable_value_labels=VARIABLE_VALUE_LABELS,
            )
        case "sav_row_compress":
            pyreadstat.write_sav(
                data,
                str(output),
                column_labels=COLUMN_LABELS,
                variable_value_labels=VARIABLE_VALUE_LABELS,
                row_compress=True
            )

    print(f"Wrote {n_obs} rows to {output}")


if __name__ == "__main__":
    main()
