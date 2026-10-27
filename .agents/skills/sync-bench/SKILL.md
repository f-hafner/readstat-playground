---
name: sync-bench
description: Keep the pyreadstat benchmark ground truth in sync with the agent-maintained DuckDB SQL approach inside src/snake/bench.py, plus the R and DuckDB SQL benchmark scripts. Use when the pyreadstat functions in src/snake/bench.py change, or when editing the *_duck functions in src/snake/bench.py, src/RRR/bench.R, src/duck/bench.sql, or src/bench/run.sh.
---

# Sync benchmarks with the pyreadstat ground truth

Inside `src/snake/bench.py`, the **pyreadstat functions are the ground truth**
(the section marked `### ground truth: pyreadstat - human edited`). The
agent-maintained `*_duck` functions in that same file, the R mirror, and the
DuckDB SQL mirror must all be updated whenever the pyreadstat ground truth
changes.

> Note: the DuckDB SQL approach lives in **two** places: the `*_duck` functions
> inside `src/snake/bench.py` (agent-edited) and `src/duck/bench.sql`. Both are
> agent-maintained mirrors of the pyreadstat ground truth and must be kept in
> sync.

## Files

| Role | Path |
|------|------|
| Ground truth (pyreadstat, human-edited) | `src/snake/bench.py` — `### ground truth: pyreadstat - human edited` section |
| Agent-maintained DuckDB mirror (Python) | `src/snake/bench.py` — `### agent-edited: loading via duckdb` section (`*_duck` functions) |
| R mirror | `src/RRR/bench.R` |
| DuckDB SQL mirror | `src/duck/bench.sql` |
| Runner / labeler | `src/bench/run.sh` |

## Procedure

1. Find out what changed in the **pyreadstat ground truth**, in this order:
   ```bash
   git diff src/snake/bench.py          # uncommitted changes
   git show HEAD -- src/snake/bench.py  # if the change was already committed
   ```
   Focus on the `### ground truth: pyreadstat - human edited` section; ignore
   changes to the `*_duck` section (those are yours to regenerate).
   If neither shows a meaningful change to the pyreadstat benchmark set (e.g.
   the commit only touched unrelated files or the output is not informative),
   **ask the user** what changed instead of guessing.
2. Identify the changed/added/removed **pyreadstat functions** and the keys in
   `benchmark_set`.
3. Update the agent-maintained mirrors to match:
   - the `*_duck` functions in `src/snake/bench.py` (one per pyreadstat
     benchmark, added to `benchmark_set` right after its pyreadstat peer),
   - the warmup sets in `src/snake/bench.py` and `src/RRR/bench.R` (see
     [Warmup](#warmup)),
   - the R mirror `src/RRR/bench.R`,
   - the SQL mirror `src/duck/bench.sql` and `src/bench/run.sh`,
   using the mapping below.
4. Run the benchmark and confirm the CSV has one row per language per key:
   ```bash
   make bench
   cat results/bench.csv
   ```

## Mapping rules

### Function and key names

- The pyreadstat ground truth defines `time_<key>()`; the agent mirror inside
  the same file defines `time_<key>_duck()` (e.g. `time_read_all` →
  `time_read_all_duck`). R defines `time_<key>` (same names, R syntax).
- `benchmark_set` keys are the canonical task names (`read_all`, `read_subset`,
  ...). The `*_duck` entries use the same key with a `_duck` suffix and sit
  directly after their pyreadstat peer. R's `benchmark_set` list must use the
  exact same base keys; SQL rows in `run.sh` must use the exact same labels.
- Keep ordering consistent: R list order and SQL query order should match the
  pyreadstat entries in Python's `benchmark_set` order.

### Reading the file

- Input path: Python `in_file = "data/test_small.sav"`; R uses the same
  `in_file`; SQL uses the same path literal.
- Full read: Python `pyreadstat.read_sav(in_file)`; the Python DuckDB mirror
  `con.sql(f"SELECT * FROM read_stat('{in_file}')").pl()`; R
  `haven::read_sav(in_file)`; SQL `FROM read_stat("data/test_small.sav")`.
- Column subset: Python
  `pyreadstat.read_sav(in_file, usecols = columns_select)`; the Python DuckDB
  mirror `con.sql(f"SELECT {','.join(columns_select)} FROM read_stat('{in_file}')").pl()`;
  R `haven::read_sav(in_file, col_select = c(...))`; SQL
  `SELECT <cols> FROM read_stat("data/test_small.sav")`.
  The column list must match the pyreadstat `usecols`/`columns_select`
  **exactly**, including order where it matters.

### Timing

- Python (both pyreadstat and `*_duck`): `time.perf_counter()`.
- R: `tictoc::tic()` / `toc(quiet = TRUE)`, then `toc_out$toc - toc_out$tic`.
- SQL: `.timer on`; `run.sh` parses the `Run Time (s): real <seconds> ...`
  lines in query order.

### Warmup

Before the timed benchmarks, Python's `main` runs a `warmup_set` whose results
are discarded (it currently warms up `read_all` and `read_all_duck`). The R
mirror reproduces this with its own `warmup_set` list, run via
`invisible(lapply(warmup_set, function(fn) fn()))`, before `benchmark_set`; R
only warms up `read_all` because it has no DuckDB variant. Warmup entries never
appear in the CSV — only `benchmark_set` is written. When adding a benchmark to
Python's `benchmark_set`, consider whether it also belongs in `warmup_set` and
mirror that in R.

Both Python and R log each set before running it, labelling the warmup entries
as `(not recorded)` and the benchmark entries as `(recorded)` so the two are
never confused in the logs.

The DuckDB SQL mirror (`src/duck/bench.sql` / `run.sh`) has **no warmup**: the
`duckdb` CLI runs as a fresh process per benchmark run, so there is nothing to
keep warm across runs.

### Output format

Long CSV: `language,task,elapsed`, appended to the file passed as the first CLI
argument. Language labels are `python`, `R`, `sql`. All three must emit the same
task keys.

## SQL specifics

There are two SQL surfaces to keep in sync:

1. The `*_duck` functions in `src/snake/bench.py` (agent-edited). They reuse
   `get_con()` to load the built extension and return `.pl()` results.
2. `src/duck/bench.sql`, run by `src/bench/run.sh`, which owns the CSV writing.
   - Add one query per benchmark key, in `benchmark_set` order, each preceded
     by a comment naming the key.
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
     `printf`/index line to `run.sh`. If SQL cannot express a benchmark,
     document the omission in both files.

## Current benchmark set

| Key | pyreadstat (ground truth) | Python `*_duck` | R | SQL |
|-----|---------------------------|-----------------|-----|-----|
| `read_all` | read every column | `SELECT * FROM read_stat(...)` | read every column | `FROM read_stat(...)` |
| `read_subset` | `usecols` / `columns_select` | `SELECT wage, person_id ...` | `col_select = c("wage", "person_id")` | `SELECT wage, person_id FROM read_stat(...)` |

### Warmup sets

| Language | Warmup entries | Where |
|----------|----------------|-------|
| Python | `read_all`, `read_all_duck` | `warmup_set` in `main` (`src/snake/bench.py`) |
| R | `read_all` | `warmup_set` in `main` (`src/RRR/bench.R`) |
| SQL | none | fresh `duckdb` CLI process per run |

## Notes

- Keep R's header comment and SQL comments describing behavior in sync with the
  actual code.
- `make bench` depends on the built extension and `data/test_small.sav`; see the
  `Makefile`.
