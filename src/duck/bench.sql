-- @@IN_FILE@@ and @@FORMAT_PARAM@@ are substituted by src/bench/run.sh with
-- data/cbs/file.<format> and an optional ", format = 'sav'" override.
-- run.sh also appends the duckdb-read-stat branch (from
-- $DUCKDB_READ_STAT_BRANCH) to every CSV row it writes.
LOAD 'duckdb-read-stat/build/release/read_stat.duckdb_extension';
.timer on
-- read_all: read every column of the whole file (the fixture has 1M rows;
-- there is no row limit anywhere).
FROM read_stat('@@IN_FILE@@'@@FORMAT_PARAM@@);
-- read_all_chunked (pyreadstat row_offset chunking) and read_all_parquet
-- (reading the file and writing parquet) are Python-only; see
-- src/RRR/bench.R for the same omissions.
-- NULLs are correct; categorical labels not converted
.quit
