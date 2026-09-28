# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy",
#     "polars",
#     "pyreadstat",
# ]
# ///
"""Create a test SPSS (.sav) or Stata (.dta) file.

Usage:
    uv run src/create_spss_file.py <n_observations> [-o OUTPUT] [--format {sav,dta}] [--seed SEED]
"""

import argparse
from pathlib import Path

import numpy as np
import polars as pl
import pyreadstat

COLUMN_LABELS: dict[str, str] = {
    "person_id": "Person identifier",
    "date": "Reference date of the event",
    "wage": "Hourly wage",
    "sector": "Economic sector",
    "null_col": "Column added later to the schema.",
}

VARIABLE_VALUE_LABELS: dict[str, dict[str | float, str]] = {
    "sector": {"1": "sector a", "2": "sector b", "3": "sector c", "99": "missing"},
    "wage": {9999999999.0: "missing", 9999999998.0: "also missing"},
}

# user-missing ranges (hi is an included bound); values in these ranges are
# stored as-is in the file and only treated as missing when read with
# user_missing=True
MISSING_RANGES: dict[str, list[dict[str, str | float]]] = {
    "sector": [{"lo": "98", "hi": "98"}],
    "wage": [{"lo": 100, "hi": 110}],
}

START_DATE = np.datetime64("2000-02-13")
END_DATE = np.datetime64("2025-12-25")


def random_dates(rng: np.random.Generator, n: int) -> np.ndarray:
    """Random dates between START_DATE and END_DATE."""
    day_range = (END_DATE - START_DATE).item().days
    deltas = rng.integers(1, day_range, n).astype("timedelta64[D]")
    return np.repeat(START_DATE, n) + deltas


def build_data(n: int, seed: int) -> pl.DataFrame:
    """Build the test dataframe with some coded missing values injected."""
    rng = np.random.default_rng(seed)
    data: dict[str, np.ndarray] = {
        # person IDs are coded as strings
        "person_id": rng.integers(1, 1_000_000_000, size=n).astype(str),
        # sav files store dates as str
        "date": random_dates(rng, n).astype(str),
        "wage": rng.random(size=n),
        # wide enough to also hold the injected missing code "99"
        "sector": rng.choice(["1", "2", "3"], size=n).astype("<U2"),
        # column that is entirely missing in the .sav file
        "null_col": np.full(n, np.nan),
    }

    possible_missing_values = {
        "sector": list(VARIABLE_VALUE_LABELS["sector"]),
        # allow 110 for the included upper bound
        "wage": [*VARIABLE_VALUE_LABELS["wage"], *np.arange(100, 111)],
    }
    n_missing = min(500, n)
    for column, values in possible_missing_values.items():
        missing_idx = rng.integers(0, n, size=n_missing)
        data[column][missing_idx] = rng.choice(values, size=n_missing)

    return pl.DataFrame(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n_obs", type=int, help="number of observations to generate")
    parser.add_argument("-o", "--output", type=Path, default=None, help="output path (default: file_in.<format>)")
    parser.add_argument("--format", choices=["sav", "dta"], default="sav", help="output file format")
    parser.add_argument("--seed", type=int, default=1234, help="random seed")
    args = parser.parse_args()

    output = args.output or Path(f"file_in.{args.format}")
    data = build_data(args.n_obs, args.seed)
    if args.format == "dta":
        # write_dta doesn't support missing_ranges
        pyreadstat.write_dta(
            data,
            str(output),
            column_labels=COLUMN_LABELS,
            variable_value_labels=VARIABLE_VALUE_LABELS,
        )
    else:
        pyreadstat.write_sav(
            data,
            str(output),
            column_labels=COLUMN_LABELS,
            variable_value_labels=VARIABLE_VALUE_LABELS,
            missing_ranges=MISSING_RANGES,
        )
    print(f"Wrote {args.n_obs} rows to {output}")


if __name__ == "__main__":
    main()

# 2. Values inside missing_ranges don't survive the write. pyreadstat stores them as system-missing, so 
# the ~400 wage values in [100, 110] come back as null and the range declaration itself isn't in the 
# file metadata. This is the same behavior your test fixture already expects, but if you wanted real 
# in-range values plus the range declaration in the file, pyreadstat won't give you that. 
