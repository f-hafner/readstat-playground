# /// script
# dependencies = [
#   "pyreadstat",
#   "polars",
#   "duckdb<2.0.0",
#   "pyarrow",
# ]
# ///

import csv
import pyreadstat
import time
from typing import Callable
import logging
import duckdb

in_file = "data/test_small.sav"
prs_output_format = "polars"
columns_select = ["wage", "person_id"]

def get_con():
    con = duckdb.connect(config={"allow_unsigned_extensions": "true"})
    con.execute("LOAD 'duckdb-read-stat/build/debug/read_stat.duckdb_extension'")
    return con

def write_to_file(results: dict[str, float], file_name: str) -> None:
    """Append results in long format."""
    with open(file_name, "a+", newline="") as csvfile:
        resultwriter = csv.writer(csvfile, delimiter=",")

        for task, elapsed in results.items():
            resultwriter.writerow(["python", task, elapsed])

### ground truth: pyreadstat - human edited
def time_read_all() -> float:
    start = time.perf_counter()
    df, meta = pyreadstat.read_sav(in_file, output_format=prs_output_format)
    end = time.perf_counter()
    elapsed = end - start
    logging.info("read_all took %.4fs", elapsed)
    return elapsed

def time_read_subset() -> float:
    start = time.perf_counter()
    df, meta = pyreadstat.read_sav(in_file, usecols=columns_select, output_format=prs_output_format)
    end = time.perf_counter()
    elapsed = end - start
    logging.info("read_subset took %.4fs", elapsed)
    return elapsed

### agent-edited: loading via duckdb
def time_read_all_duck() -> float:
    con = get_con()
    start = time.perf_counter()
    df = con.sql(f"SELECT * FROM read_stat('{in_file}')").pl()
    end = time.perf_counter()
    elapsed = end - start
    logging.info("read_all_duck took %.4fs", elapsed)
    return elapsed

def time_read_subset_duck() -> float:
    con = get_con()
    start = time.perf_counter()
    df = con.sql(f"SELECT {','.join(columns_select)} FROM read_stat('{in_file}')").pl()
    end = time.perf_counter()
    elapsed = end - start
    logging.info("read_subset_duck took %.4fs", elapsed)
    return elapsed

def main(file_name: str) -> None:
    logging.info("language: python")
    benchmark_set: dict[str, Callable] = {
            "read_all": time_read_all,
            "read_all_duck": time_read_all_duck,
            "read_subset": time_read_subset,
            "read_subset_duck": time_read_subset_duck,
    }
    logging.info("running benchmarks: %s", list(benchmark_set))
    results = {fn_name: fn() for fn_name, fn in benchmark_set.items()}
    logging.info("writing results to %s", file_name)
    write_to_file(results, file_name)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    result_file = sys.argv[1]
    main(result_file)
