#!/bin/bash
# Benchmark runner: for every format, run the Python, R, and DuckDB clients on
# data/cbs/file.<format> and append one CSV row per benchmarked (task, tool)
# pair. read_all and read_all_chunked are currently disabled in all clients.
#
# The branch of the duckdb-read-stat submodule is exported as
# DUCKDB_READ_STAT_BRANCH and appended to every row (bench.py and bench.R read
# it too), so results from different branches stay distinguishable.
#
# read_all_chunked (pyreadstat row_offset chunking) and read_all_parquet
# (parquet sink) are Python-only; see src/duck/bench.sql for the omissions.
#
declare CSV=${1:-results/bench.csv}
declare FORMATS=${2:-sav sav_row_compress dta}
# Dataset label written to the results csv (all files live in data/cbs).
declare SIZE=cbs
declare BRANCH=${DUCKDB_READ_STAT_BRANCH:-$(git -C duckdb-read-stat rev-parse --abbrev-ref HEAD)}
export DUCKDB_READ_STAT_BRANCH="$BRANCH"

for FORMAT in $FORMATS; do
  declare IN_FILE="data/cbs/file.$FORMAT"
  export IN_FILE FORMAT SIZE

  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO format: $FORMAT size: $SIZE"
  uv run src/snake/bench.py "$CSV" "$FORMAT"

  Rscript src/RRR/bench.R "$CSV" "$FORMAT"

  # Row-compressed SPSS files need an explicit format override.
  if [ "$FORMAT" = "sav_row_compress" ]; then
    FORMAT_PARAM=", format = 'sav'"
  else
    FORMAT_PARAM=""
  fi

  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO language: duckdb"
  mapfile -t duckdb_times < <(sed \
    -e "s|@@IN_FILE@@|${IN_FILE}|g" \
    -e "s|@@FORMAT_PARAM@@|${FORMAT_PARAM}|g" \
    src/duck/bench.sql \
    | duckdb -unsigned \
    | sed -nE 's/^Run Time \(s\): real ([0-9.]+) .*/\1/p')
  printf "%s,%s,%s,%s,%s,%s,%s\n" sql read_all duckdb "$FORMAT" "$SIZE" "${duckdb_times[0]}" "$BRANCH" >> "$CSV"
done
