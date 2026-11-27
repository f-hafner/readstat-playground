"""Time pyreadstat chunked reads against DuckDB for growing datasets.

Both readers stream the whole file and discard the batches, so the measurement
covers parsing/reading without materializing hundreds of millions of rows in
memory. Results are appended in the same long format as results/bench.csv:

    language,task,tool,format,size,timing,branch

`size` is the row-count label (100k, 1m, 10m, 50m) and `--format` selects the
file type. By default the files are the row-compressed .sav files created by
`src/snake/create_scaling_stat_file.py` in data/scaling/; `--format sas7bdat`
uses SAS fixtures if they are available.

Usage:
    uv run src/snake/create_scaling_stat_file.py
    uv run src/snake/bench_scaling.py
    uv run src/snake/bench_scaling.py results/bench_scaling.csv --sizes 100k 1m
    uv run src/snake/bench_scaling.py --format sas7bdat --sizes 100k 1m 10m
"""

# /// script
# dependencies = [
#   "duckdb<2.0.0",
#   "polars",
#   "pyarrow",
#   "pyreadstat",
#   "tqdm",
# ]
# ///

from __future__ import annotations

import argparse
import csv
import logging
import time
from pathlib import Path
from typing import Iterable
from tqdm import tqdm

import duckdb
import pyreadstat

from readers import extension_branch

# Keep in sync with src/snake/create_scaling_stat_file.py.
SIZES: dict[str, int] = {
    "100k": 100_000,
    "1m": 1_000_000,
    "10m": 10_000_000,
    "50m": 50_000_000,
}
# 50m is opt-in: it is slow to benchmark.
DEFAULT_SIZES = ["100k", "1m", "10m"]

FILE_FORMATS = ("sav_row_compress", "sas7bdat")
DEFAULT_FILE_FORMAT = "sav_row_compress"
EXTENSION_PATH = "duckdb-read-stat/build/release/read_stat.duckdb_extension"
BAR_FORMAT = (
    "{l_bar}{bar}| {n_fmt}/{total_fmt} chunks "
    "[{elapsed}<{remaining}, {rate_inv_fmt}]"
)


def file_name(label: str, file_format: str = DEFAULT_FILE_FORMAT) -> str:
    """Name of the scaling file for a size label and format."""
    return f"test_{label}.{file_format}"


def pyreadstat_reader(file_format: str):
    """Return the pyreadstat reader used by the chunked benchmark."""
    if file_format == "sas7bdat":
        return pyreadstat.read_sas7bdat
    return pyreadstat.read_sav


def get_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(config={"allow_unsigned_extensions": "true"})
    con.execute(f"LOAD '{EXTENSION_PATH}'")
    return con


def read_stat_call(path: Path, file_format: str = DEFAULT_FILE_FORMAT) -> str:
    """read_stat() call for a scaling file."""
    safe_path = str(path).replace("'", "''")
    # The extension does not recognize the .sav_row_compress extension.
    if file_format == "sav_row_compress":
        return f"read_stat('{safe_path}', format='sav')"
    return f"read_stat('{safe_path}')"


def time_pyreadstat_chunked(
    path: Path, file_format: str, chunksize: int, n_rows: int
) -> tuple[float, int]:
    """Stream a file with pyreadstat chunks; return elapsed seconds and rows."""
    rows = 0
    total_chunks = (n_rows + chunksize - 1) // chunksize
    start = time.perf_counter()
    chunks = pyreadstat.read_file_in_chunks(
        pyreadstat_reader(file_format),
        str(path),
        chunksize=chunksize,
        output_format="polars",
    )
    for chunk, _meta in tqdm(
        chunks,
        total=total_chunks,
        desc=f"pyreadstat {path.name}",
        unit="chunk",
        bar_format=BAR_FORMAT,
    ):
        rows += chunk.height
    return time.perf_counter() - start, rows


def time_duckdb(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    file_format: str,
    chunksize: int,
    n_rows: int,
) -> tuple[float, int]:
    """Stream a file with DuckDB record batches; return elapsed seconds and rows."""
    total_chunks = (n_rows + chunksize - 1) // chunksize
    start = time.perf_counter()
    batches = con.execute(
        f"SELECT * FROM {read_stat_call(path, file_format)}"
    ).to_arrow_reader(chunksize)
    rows = sum(
        batch.num_rows
        for batch in tqdm(
            batches,
            total=total_chunks,
            desc=f"duckdb {path.name}",
            unit="chunk",
            bar_format=BAR_FORMAT,
        )
    )
    return time.perf_counter() - start, rows


def warmup(
    path: Path, file_format: str, con: duckdb.DuckDBPyConnection, chunksize: int
) -> None:
    """Warm up imports/conversions with a single chunk of the smallest file."""
    for _chunk, _meta in pyreadstat.read_file_in_chunks(
        pyreadstat_reader(file_format),
        str(path),
        chunksize=chunksize,
        limit=chunksize,
        output_format="polars",
    ):
        break
    con.execute(
        f"SELECT * FROM {read_stat_call(path, file_format)} LIMIT 1"
    ).fetchall()


def write_rows(
    file_name: str,
    file_format: str,
    entries: Iterable[tuple[str, str, float]],
) -> None:
    """Append (tool, size, elapsed) rows to the long-format CSV."""
    branch = extension_branch()
    with open(file_name, "a+", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=",")
        for tool, size, elapsed in entries:
            writer.writerow(
                ["python", "read_all", tool, file_format, size, elapsed, branch]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv", nargs="?", default="results/bench_scaling.csv", type=Path
    )
    parser.add_argument(
        "--format",
        dest="file_format",
        choices=FILE_FORMATS,
        default=DEFAULT_FILE_FORMAT,
        help=f"input file format (default: {DEFAULT_FILE_FORMAT})",
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        choices=list(SIZES),
        default=DEFAULT_SIZES,
        help=f"size labels to benchmark (default: {' '.join(DEFAULT_SIZES)})",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/scaling"), help="input directory"
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=100_000,
        help="chunk/batch size for both readers (default: 100000)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="measurements per size and tool (default: 1)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.info("language: python")

    selected = sorted(args.sizes, key=SIZES.get)
    paths = {
        size: args.data_dir / file_name(size, args.file_format)
        for size in selected
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise SystemExit(
            "missing input files:\n  "
            + "\n  ".join(missing)
            + "\nrun src/snake/create_scaling_stat_file.py first"
            " (or copy the sas7bdat fixtures from sas_data/)"
        )

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    con = get_con()
    warmup(paths[selected[0]], args.file_format, con, args.chunksize)

    for size in selected:
        path = paths[size]
        expected_rows = SIZES[size]
        for repeat in range(args.repeats):
            # Alternate the order so page-cache effects do not systematically
            # favour one tool.
            duck_first = repeat % 2 == 1
            if duck_first:
                duck_elapsed, duck_rows = time_duckdb(
                    con, path, args.file_format, args.chunksize, expected_rows
                )
                prs_elapsed, prs_rows = time_pyreadstat_chunked(
                    path, args.file_format, args.chunksize, expected_rows
                )
            else:
                prs_elapsed, prs_rows = time_pyreadstat_chunked(
                    path, args.file_format, args.chunksize, expected_rows
                )
                duck_elapsed, duck_rows = time_duckdb(
                    con, path, args.file_format, args.chunksize, expected_rows
                )

            entries: list[tuple[str, float]] = []
            for tool, elapsed, rows in (
                ("pyreadstat_chunked", prs_elapsed, prs_rows),
                ("duckdb", duck_elapsed, duck_rows),
            ):
                if rows != expected_rows:
                    logging.warning(
                        "%s read %s rows, expected %s",
                        tool,
                        f"{rows:,}",
                        f"{expected_rows:,}",
                    )
                logging.info(
                    "%s: %s rows in %.4fs (%s)",
                    tool,
                    f"{expected_rows:,}",
                    elapsed,
                    f"repeat {repeat + 1}/{args.repeats}",
                )
                entries.append((tool, elapsed))
            write_rows(
                str(args.csv),
                args.file_format,
                [(tool, size, elapsed) for tool, elapsed in entries],
            )

    con.close()
    logging.info("wrote results to %s", args.csv)


if __name__ == "__main__":
    main()
