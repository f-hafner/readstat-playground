"""Benchmark pyreadstat against DuckDB on data/cbs/file.<format>.

Warmup is necessary because both duckdb and pyreadstat import modules
(polars/pyarrow) lazily on first use.

Usage:
    uv run src/snake/bench.py <result_file> [sav|sav_row_compress|dta]
"""

# /// script
# dependencies = [
#   "pyreadstat",
#   "polars",
#   "duckdb<2.0.0",
#   "pyarrow",
#   "tqdm",
# ]
# ///

import csv
import functools
import logging
import tempfile
import time
from pathlib import Path
from typing import Callable

from readers import (
    DEFAULT_CHUNKSIZE,
    extension_branch,
    get_con,
    number_of_rows,
    read_all_duckdb,
    read_all_parquet_duckdb,
    read_all_parquet_pyreadstat,
    read_all_pyreadstat,
    read_all_pyreadstat_chunked,
    resolve_in_file,
)

# Dataset label written to the results csv (the files all live in data/cbs).
DATASET = "cbs"


def write_to_file(results: dict[tuple[str, str], float], file_format: str, file_name: str) -> None:
    """Append results in long format (branch = branch of the extension)."""
    branch = extension_branch()
    with open(file_name, "a+", newline="") as csvfile:
        resultwriter = csv.writer(csvfile, delimiter=",")
        for (task, tool), elapsed in results.items():
            resultwriter.writerow(
                ["python", task, tool, file_format, DATASET, elapsed, branch]
            )


### ground truth: pyreadstat - human edited
def time_read_all(in_file: str, file_format: str) -> float:
    start = time.perf_counter()
    read_all_pyreadstat(in_file, file_format)
    elapsed = time.perf_counter() - start
    logging.info("read_all took %.4fs", elapsed)
    return elapsed


def time_read_all_chunked(in_file: str, file_format: str, n_rows: int) -> float:
    start = time.perf_counter()
    read_all_pyreadstat_chunked(in_file, file_format, n_rows, DEFAULT_CHUNKSIZE)
    elapsed = time.perf_counter() - start
    logging.info("read_all_chunked took %.4fs", elapsed)
    return elapsed


def time_read_all_parquet(
    in_file: str, file_format: str, output_path: Path
) -> float:
    start = time.perf_counter()
    read_all_parquet_pyreadstat(in_file, file_format, output_path)
    elapsed = time.perf_counter() - start
    logging.info("read_all_parquet took %.4fs", elapsed)
    return elapsed


### agent-edited: loading via duckdb
def time_read_all_duckdb(in_file: str, file_format: str, n_rows: int) -> float:
    con = get_con()  # connection setup stays outside the timed region
    start = time.perf_counter()
    read_all_duckdb(con, in_file, file_format, n_rows, DEFAULT_CHUNKSIZE)
    elapsed = time.perf_counter() - start
    logging.info("read_all_duck took %.4fs", elapsed)
    return elapsed


def time_read_all_parquet_duckdb(
    in_file: str, file_format: str, output_path: Path
) -> float:
    # parallel=True: only this task gives up insertion order, so COPY can write
    # one parquet file per thread.
    con = get_con(parallel=True)  # connection setup stays outside the timed region
    start = time.perf_counter()
    read_all_parquet_duckdb(con, in_file, file_format, output_path)
    elapsed = time.perf_counter() - start
    logging.info("read_all_parquet_duck took %.4fs", elapsed)
    return elapsed


### warmup
# The whole file is read (there is no row limit anywhere); results are discarded.
def warmup_read(in_file: str, file_format: str) -> None:
    read_all_pyreadstat(in_file, file_format)


def warmup_read_duckdb(in_file: str, file_format: str, n_rows: int) -> None:
    read_all_duckdb(get_con(), in_file, file_format, n_rows, DEFAULT_CHUNKSIZE)


def main(file_name: str, file_format: str = "sav") -> None:
    in_file = resolve_in_file(file_format)
    # Metadata only, outside the timed region: the readers get the row count as
    # an argument so it does not count as benchmark work.
    n_rows = number_of_rows(in_file, file_format)
    logging.info("language: python")
    logging.info(
        "reading %s (format: %s, rows: %d, chunksize: %d)",
        in_file,
        file_format,
        n_rows,
        DEFAULT_CHUNKSIZE,
    )

    # Warmup reads the whole file too; results are discarded.
    warmup_set: dict[str, Callable[[], None]] = {
        "read_all": functools.partial(warmup_read, str(in_file), file_format),
        "read_all_duckdb": functools.partial(
            warmup_read_duckdb, str(in_file), file_format, n_rows
        ),
    }
    logging.info("running warmup (not recorded): %s", list(warmup_set))
    _ = {fn_name: fn() for fn_name, fn in warmup_set.items()}

    # Parquet sinks write into a temporary directory that is removed when the
    # session (this `with` block) ends.
    with tempfile.TemporaryDirectory(prefix="read-stat-bench-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        benchmark_set: dict[tuple[str, str], Callable[[], float]] = {
            ("read_all", "pyreadstat"): functools.partial(time_read_all, str(in_file), file_format),
            #("read_all_chunked", "pyreadstat"): functools.partial(time_read_all_chunked, str(in_file), file_format, n_rows),
            ("read_all", "duckdb"): functools.partial(time_read_all_duckdb, str(in_file), file_format, n_rows),
            ("read_all_parquet", "pyreadstat"): functools.partial(time_read_all_parquet, str(in_file), file_format, tmp_path / "pyreadstat.parquet"),
            ("read_all_parquet", "duckdb"): functools.partial(time_read_all_parquet_duckdb, str(in_file), file_format, tmp_path / "duckdb"),
        }
        logging.info("running benchmarks (recorded): %s", list(benchmark_set))
        results = {fn_name: fn() for fn_name, fn in benchmark_set.items()}
        logging.info("writing results to %s", file_name)
        write_to_file(results, file_format, file_name)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: bench.py <result_file> [sav|sav_row_compress|dta]"
        )
    result_file = sys.argv[1]
    file_format = sys.argv[2] if len(sys.argv) > 2 else "sav"
    main(result_file, file_format)
