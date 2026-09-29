# /// script
# dependencies = [
#   "pyreadstat",
#   "pandas",
# ]
# ///

import csv
import pyreadstat
import time
from typing import Callable
import logging

in_file = "data/test_small.sav"


def write_to_file(results: dict[str, float], file_name: str) -> None:
    """Append results in long format."""
    with open(file_name, "a+", newline="") as csvfile:
        resultwriter = csv.writer(csvfile, delimiter=",")

        for task, elapsed in results.items():
            resultwriter.writerow(["python", task, elapsed])


def time_read() -> float:
    start = time.perf_counter()
    df, meta = pyreadstat.read_sav(in_file)
    end = time.perf_counter()
    elapsed = end - start
    logging.info("read took %.4fs", elapsed)
    return elapsed


def main(file_name: str) -> None:
    logging.info("language: python")
    benchmark_set: dict[str, Callable] = {"read": time_read}
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
