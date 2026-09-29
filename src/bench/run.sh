#!/bin/bash
# TODO: add script creation in python
#
declare CSV=${1:-results/bench.csv}

uv run src/snake/bench.py "$CSV"

Rscript src/RRR/bench.R "$CSV"

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO language: duckdb"
duckdb_read=$(duckdb -unsigned < src/duck/bench.sql | tail -1 | sed -E "s/.+real ([0-9.]+) .+/\1/")
printf "%s,%s,%s\n" sql read "$duckdb_read" >> "$CSV"
