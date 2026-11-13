LOAD 'duckdb-read-stat/build/reldebug/read_stat.duckdb_extension';
SET threads=1;
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
SELECT count(*) FROM read_stat('data/test_small.sav');
.quit
