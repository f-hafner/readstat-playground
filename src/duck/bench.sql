-- INSTALL read_stat FROM community;
LOAD 'duckdb-read-stat/build/debug/read_stat.duckdb_extension';
.timer on
FROM read_stat("data/test_small.sav"); 
-- NULLs are correct; categorical labels not converted
.quit
