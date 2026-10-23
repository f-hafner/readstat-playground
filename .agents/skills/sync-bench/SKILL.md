---
name: sync-bench
description: Keep the R and DuckDB SQL benchmark scripts in sync with the Python benchmark ground truth in src/snake/bench.py. Use when src/snake/bench.py changes, or when editing src/RRR/bench.R, src/duck/bench.sql, or src/bench/run.sh.
---

# Sync benchmarks with Python ground truth

`src/snake/bench.py` is the **ground truth** for the benchmark suite. The R and
SQL implementations are mirrors and must be updated whenever Python changes.

## Files

| Role | Path |
|------|------|
| Ground truth | `src/snake/bench.py` |
| R mirror | `src/RRR/bench.R` |
| DuckDB SQL mirror | `src/duck/bench.sql` |
| Runner / labeler | `src/bench/run.sh` |

## Procedure

1. Find out what changed in the Python benchmark, in this order:
   ```bash
   git diff src/snake/bench.py          # uncommitted changes
   git show HEAD -- src/snake/bench.py  # if the change was already committed
   ```
   If neither shows a meaningful change to the benchmark set (e.g. the commit
   only touched unrelated files or the output is not informative), **ask the
   user** what changed instead of guessing.
2. Identify the changed/added/removed benchmark **functions** and the keys in
   `benchmark_set`.
3. Apply the same change to R and SQL using the mapping below.
4. Run the benchmark and confirm the CSV has one row per language per key:
   ```bash
   make bench
   cat results/bench.csv
   ```

## Mapping rules

### Function and key names

- Python defines `time_<key>()`; R defines `time_<key>` (same names, R syntax).
- Python's `benchmark_set` dict keys are the canonical task names
  (`read_all`, `read_subset`, ...). R's `benchmark_set` list must use the exact
  same keys; SQL rows in `run.sh` must use the exact same labels.
- Keep ordering consistent: R list order and SQL query order should match
  Python's `benchmark_set` order.

### Reading the file

- Input path: Python `in_file = "data/test_small.sav"`; R uses the same
  `in_file`; SQL uses the same path literal.
- Full read: Python `pyreadstat.read_sav(in_file)`; R
  `haven::read_sav(in_file)`; SQL `FROM read_stat("data/test_small.sav")`.
- Column subset: Python `pyreadstat.read_sav(in_file, usecols = c(...))`; R
  `haven::read_sav(in_file, col_select = c(...))`; SQL
  `SELECT <cols> FROM read_stat("data/test_small.sav")`.
  The column list must match Python's `usecols` **exactly**, including order
  where it matters.

### Timing

- Python: `time.perf_counter()`.
- R: `tictoc::tic()` / `toc(quiet = TRUE)`, then `toc_out$toc - toc_out$tic`.
- SQL: `.timer on`; `run.sh` parses the `Run Time (s): real <seconds> ...`
  lines in query order.

### Output format

Long CSV: `language,task,elapsed`, appended to the file passed as the first CLI
argument. Language labels are `python`, `R`, `sql`. All three must emit the same
task keys.

## SQL specifics

`src/duck/bench.sql` is run by `src/bench/run.sh`, which owns the CSV writing:

- Add one query per benchmark key, in `benchmark_set` order, each preceded by a
  comment naming the key.
- `run.sh` extracts all `real` times with:
  ```bash
  mapfile -t duckdb_times < <(duckdb -unsigned < src/duck/bench.sql \
    | sed -nE 's/^Run Time \(s\): real ([0-9.]+) .*/\1/p')
  ```
- Then writes one row per key, e.g.:
  ```bash
  printf "%s,%s,%s\n" sql read_all    "${duckdb_times[0]}" >> "$CSV"
  printf "%s,%s,%s\n" sql read_subset "${duckdb_times[1]}" >> "$CSV"
  ```
- When adding a benchmark, add its query to `bench.sql` **and** its
  `printf`/index line to `run.sh`. If SQL cannot express a benchmark, document
  the omission in both files.

## Current benchmark set

| Key | Python / R call | SQL |
|-----|-----------------|-----|
| `read_all` | read every column | `FROM read_stat(...)` |
| `read_subset` | `usecols` / `col_select = c("wage", "person_id")` | `SELECT wage, person_id FROM read_stat(...)` |

## Notes

- Keep R's header comment and SQL comments describing behavior in sync with the
  actual code.
- `make bench` depends on the built extension and `data/test_small.sav`; see the
  `Makefile`.
