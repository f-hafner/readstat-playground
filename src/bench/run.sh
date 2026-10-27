#!/bin/bash
# TODO: add script creation in python
#
declare CSV=${1:-results/bench.csv}

uv run src/snake/bench.py "$CSV"

Rscript src/RRR/bench.R "$CSV"

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO language: duckdb"
mapfile -t duckdb_times < <(duckdb -unsigned < src/duck/bench.sql \
  | sed -nE 's/^Run Time \(s\): real ([0-9.]+) .*/\1/p')
printf "%s,%s,%s,%s\n" sql read_all duckdb "${duckdb_times[0]}" >> "$CSV"
printf "%s,%s,%s,%s\n" sql read_subset duckdb "${duckdb_times[1]}" >> "$CSV"
