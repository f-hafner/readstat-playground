"""Readers for the cbs benchmark file (data/cbs/file.<format>).

One reader per tool:
- DuckDB, through the read_stat() extension, consumed as Arrow batches
- pyreadstat, reading the whole file at once
- pyreadstat, chunked manually with row_offset/row_limit

The manual chunking is intentional: pyreadstat's read_file_in_chunks() is not
used here. Every chunk read re-opens the file and skips `row_offset` rows, so
this measures the cost of "read a slice at a time" rather than pyreadstat's
own chunked implementation.
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

from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path
from typing import Callable

import duckdb
import polars as pl
import pyarrow.parquet as pq
import pyreadstat
from tqdm import tqdm

import logging

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/cbs")
EXTENSION_DIR = Path("duckdb-read-stat")
EXTENSION_PATH = "duckdb-read-stat/build/release/read_stat.duckdb_extension"
# src/bench/run.sh exports this so the R and SQL clients report the same branch.
BRANCH_ENV_VAR = "DUCKDB_READ_STAT_BRANCH"
# pyreadstat reader per format. `sav` and `sav_row_compress` are both SPSS
# files, so they share pyreadstat.read_sav.
READERS: dict[str, Callable] = {
    "sav": pyreadstat.read_sav,
    "sav_row_compress": pyreadstat.read_sav,
    "dta": pyreadstat.read_dta,
}
FORMATS = tuple(READERS)
OUTPUT_FORMAT = "polars"
DEFAULT_CHUNKSIZE = 500_000


def extension_branch() -> str:
    """Branch the read_stat extension was built from.

    $DUCKDB_READ_STAT_BRANCH overrides the git lookup (set by `make` and
    src/bench/run.sh so every client records the same value).
    """
    if branch := os.environ.get(BRANCH_ENV_VAR):
        return branch
    try:
        result = subprocess.run(
            ["git", "-C", str(EXTENSION_DIR), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def resolve_in_file(file_format: str) -> Path:
    """Path of the cbs file for the given format; $IN_FILE takes precedence."""
    if env_file := os.environ.get("IN_FILE"):
        return Path(env_file)
    if file_format not in FORMATS:
        raise SystemExit(
            f"unknown format {file_format!r}; choose from {', '.join(FORMATS)}"
        )
    return DATA_DIR / f"file.{file_format}"


def get_con(parallel: bool = False) -> duckdb.DuckDBPyConnection:
    """DuckDB connection with the read_stat extension loaded.

    `parallel=True` disables insertion-order preservation, which is what lets
    `COPY ... (PER_THREAD_OUTPUT true)` write one file per thread instead of
    funnelling every row through a single ordered sink. Only the
    read_all_parquet sink uses it; the read-only tasks keep the default
    (ordered) behavior so their row order still matches the source file.
    """
    con = duckdb.connect(config={"allow_unsigned_extensions": "true"})
    if parallel:
        con.sql("SET THREADS TO 4")
    else:
        con.sql("SET THREADS TO 1")

    n_threads = con.sql("SELECT current_setting('threads')").fetchall()[0][0]
    logger.info(f"DuckDB is running with {n_threads} threads.")
    if parallel:
        con.sql("SET preserve_insertion_order=false")
    con.execute(f"LOAD '{EXTENSION_PATH}'")
    return con


def read_stat_call(in_file: str | Path, file_format: str) -> str:
    """Build the read_stat() call, overriding the format when needed.

    Row-compressed SPSS files use a .sav_row_compress extension that the
    extension does not recognize, so the format has to be passed explicitly.
    """
    if file_format == "sav_row_compress":
        return f"read_stat('{in_file}', format='sav')"
    return f"read_stat('{in_file}')"


def read_all_duckdb(
    con: duckdb.DuckDBPyConnection,
    in_file: str | Path,
    file_format: str,
    n_rows: int,
    chunksize: int = DEFAULT_CHUNKSIZE,
) -> None:
    """Read every column with DuckDB, `chunksize` rows at a time.

    The result is pulled as Arrow record batches instead of being materialized
    with .pl(), so memory stays bounded the same way as the chunked pyreadstat
    reader. A real job would write each batch to parquet; only the read is
    done here, and every batch is discarded.

    `n_rows` is only used for the progress bar total; the caller discovers it
    (see `number_of_rows()`) so the metadata read is not part of the benchmark.
    """
    n_batches = math.ceil(n_rows / chunksize)
    batches = con.sql(
        f"SELECT * FROM {read_stat_call(in_file, file_format)}"
    ).fetch_record_batch(rows_per_batch=chunksize)
    for _batch in tqdm(
        batches, total=n_batches, desc="read_all_duck", unit="batch", disable=None
    ):
        pass


def pyreadstat_reader(file_format: str) -> Callable:
    """Return the pyreadstat reader for the given format."""
    if file_format not in READERS:
        raise SystemExit(
            f"unknown format {file_format!r}; choose from {', '.join(FORMATS)}"
        )
    return READERS[file_format]


def number_of_rows(in_file: str | Path, file_format: str) -> int:
    """Number of rows in the file, read from the metadata only.

    Call this outside the timed region (in `bench.py`) and pass the result to
    the readers, so the metadata read does not count as benchmark work.
    """
    _data, meta = pyreadstat_reader(file_format)(
        str(in_file), metadataonly=True, output_format=OUTPUT_FORMAT
    )
    return meta.number_rows


def pyreadstat_frame(in_file: str | Path, file_format: str) -> pl.DataFrame:
    """Read every row with pyreadstat into a polars dataframe."""
    data, _meta = pyreadstat_reader(file_format)(
        str(in_file), output_format=OUTPUT_FORMAT
    )
    return data


def read_all_pyreadstat(in_file: str | Path, file_format: str) -> None:
    """Read every column with pyreadstat in a single call; discard the data."""
    pyreadstat_frame(in_file, file_format)


def read_all_parquet_pyreadstat(
    in_file: str | Path, file_format: str, output_path: str | Path
) -> None:
    """Read every row with pyreadstat and write them to parquet.

    The polars dataframe is written with pyarrow's ParquetWriter.
    """
    table = pyreadstat_frame(in_file, file_format).to_arrow()
    with pq.ParquetWriter(str(output_path), table.schema) as writer:
        writer.write_table(table)


def read_all_parquet_duckdb(
    con: duckdb.DuckDBPyConnection,
    in_file: str | Path,
    file_format: str,
    output_path: str | Path,
) -> None:
    """Read every row with DuckDB and write it to parquet.

    `output_path` is a directory: PER_THREAD_OUTPUT lets every DuckDB thread
    write its own parquet file, so the write can run in parallel. The
    connection must have been opened with `get_con(parallel=True)`, otherwise
    DuckDB preserves row order and serializes the write into a single file.
    """
    con.execute(
        f"COPY (SELECT * FROM {read_stat_call(in_file, file_format)}) "
        f"TO '{output_path}' (FORMAT parquet, PER_THREAD_OUTPUT true)"
    )


def read_all_pyreadstat_chunked(
    in_file: str | Path,
    file_format: str,
    n_rows: int,
    chunksize: int = DEFAULT_CHUNKSIZE,
) -> None:
    """Read every column with pyreadstat, one row_offset slice at a time.

    A real job would write each batch to parquet; only the read is done here,
    and the data is discarded. `n_rows` comes from the caller (discovered via
    `number_of_rows()` in `bench.py`) so it is not part of the benchmark.
    """
    reader = pyreadstat_reader(file_format)
    for offset in tqdm(
        range(0, n_rows, chunksize),
        desc="read_all_chunked",
        unit="batch",
        disable=None,
    ):
        reader(
            str(in_file),
            row_offset=offset,
            row_limit=min(chunksize, n_rows - offset),
            output_format=OUTPUT_FORMAT,
        )
