-- INSTALL read_stat FROM community;
LOAD 'duckdb-read-stat/build/debug/read_stat.duckdb_extension';
.timer on
-- read_all: read every column
FROM read_stat("data/test_small.sav");
-- read_subset: project down to two columns
SELECT wage, person_id FROM read_stat("data/test_small.sav");
-- NULLs are correct; categorical labels not converted
.quit
