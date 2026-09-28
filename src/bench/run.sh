
# TODO: add script creation in python
#
#rm -rf results/bench.csv
uv run src/snake/bench.py results/bench.csv
#
Rscript src/RRR/bench.R results/bench.csv

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO language: duckdb"
duckdb_read=$(duckdb < src/duck/bench.sql | tail -1 | sed -E "s/.+real ([0-9.]+) .+/\1/")
printf "%s,%s,%s\n" sql read "$duckdb_read" >> results/bench.csv



