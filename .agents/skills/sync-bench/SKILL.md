---
name: sync-bench
description: Keep the pyreadstat benchmark ground truth in sync with the agent-maintained DuckDB SQL approach inside src/snake/bench.py, plus the R (haven + DuckDB) and DuckDB SQL benchmark scripts. Use when the pyreadstat functions in src/snake/bench.py change, or when editing the *_duck functions in src/snake/bench.py, src/RRR/bench.R, src/duck/bench.sql, or src/bench/run.sh.
---

# Sync benchmarks with the pyreadstat ground truth

Inside `src/snake/bench.py`, the **pyreadstat functions are the ground truth**
(the section marked `### ground truth: pyreadstat - human edited`). The
agent-maintained `*_duck` functions in that same file, the R mirror (both its
haven and DuckDB variants), and the DuckDB SQL mirror must all be updated
whenever the pyreadstat ground truth changes.

> Note: the DuckDB SQL approach lives in **three** places: the `*_duck`
> functions inside `src/snake/bench.py` (agent-edited), the `*_duck` functions
> in `src/RRR/bench.R` (via the R `duckdb` package), and `src/duck/bench.sql`.
> All are agent-maintained mirrors of the pyreadstat ground truth and must be
> kept in sync.

## Files

| Role | Path |
|------|------|
| Ground truth (pyreadstat, human-edited) | `src/snake/bench.py` — `### ground truth: pyreadstat - human edited` section |
| Agent-maintained DuckDB mirror (Python) | `src/snake/bench.py` — `### agent-edited: loading via duckdb` section (`*_duck` functions) |
| R mirror (haven + DuckDB) | `src/RRR/bench.R` |
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
2. Identify the changed/added/removed **pyreadstat functions** and the
   `(task, tool)` entries in `benchmark_set`.
3. Update the agent-maintained mirrors to match:
   - the `*_duck` functions in `src/snake/bench.py` (one per pyreadstat
     benchmark, added to `benchmark_set` after the pyreadstat block),
   - the warmup sets in `src/snake/bench.py` and `src/RRR/bench.R` (see
     [Warmup](#warmup)),
   - the R mirror `src/RRR/bench.R`, which now has both a haven and a DuckDB
     variant per benchmark,
   - the SQL mirror `src/duck/bench.sql` and `src/bench/run.sh`,
   using the mapping below.
4. Run the benchmark and confirm the CSV has one row per language per
   `(task, tool)` pair:
   ```bash
   make bench
   cat results/bench.csv
   ```

## Mapping rules

### Function and key names

- The pyreadstat ground truth defines `time_<task>()`; the agent mirror inside
  the same file defines `time_<task>_duck()` (e.g. `time_read_all` →
  `time_read_all_duck`). R defines `time_<task>` for the haven variant and
  `time_<task>_duck` for the DuckDB variant (same names as Python).
- Python's `benchmark_set` is keyed by `(task, tool)` tuples, where `task` is
  the canonical task name (`read_all`, `read_subset`, ...) and `tool` is the
  implementation label (`pyreadstat`, `duckdb`). Current order:
  `(read_all, pyreadstat)`, `(read_subset, pyreadstat)`, `(read_all, duckdb)`,
  `(read_subset, duckdb)`.
- R's `benchmark_set` is a list of entries of the form
  `list(task = ..., tool = ..., fn = ...)`. Use the same `task` labels as
  Python and keep the order identical; the R tools are `haven` (ground truth)
  and `duckdb`.
- SQL rows in `run.sh` use the same task names (without the `_duck` suffix)
  and the tool label `duckdb`, matching the DuckDB tool label used by the
  Python and R clients.
- Keep ordering consistent: R's `benchmark_set` order must match Python's
  exactly, and SQL query order must match the pyreadstat entries in that same
  order.

### Reading the file

- Input path: Python `in_file = "data/test_small.sav"`; R uses the same
  `in_file`; SQL uses the same path literal.
- Extension path (DuckDB): Python's `get_con()` and R's `get_con()` both load
  `duckdb-read-stat/build/debug/read_stat.duckdb_extension` via a relative path
  (`extension_path` in R); SQL loads it with `LOAD` at the top of the script.
- Full read: Python `pyreadstat.read_sav(in_file)`; the Python DuckDB mirror
  `con.sql(f"SELECT * FROM read_stat('{in_file}')").pl()`; R haven
  `haven::read_sav(in_file)`; R DuckDB
  `DBI::dbGetQuery(con, sprintf("SELECT * FROM read_stat('%s')", in_file))`;
  SQL `FROM read_stat("data/test_small.sav")`.
- Column subset: Python
  `pyreadstat.read_sav(in_file, usecols = columns_select)`; the Python DuckDB
  mirror `con.sql(f"SELECT {','.join(columns_select)} FROM read_stat('{in_file}')").pl()`;
  R haven `haven::read_sav(in_file, col_select = columns_select)`; R DuckDB
  `SELECT <columns_select joined with ", "> FROM read_stat('<in_file>')`; SQL
  `SELECT <cols> FROM read_stat("data/test_small.sav")`.
  The column list must match the pyreadstat `usecols`/`columns_select`
  **exactly**, including order where it matters. Keep R's `columns_select`
  vector in sync with Python's `columns_select` list.

### Timing

- Python (both pyreadstat and `*_duck`): `time.perf_counter()`.
- R (both haven and `*_duck`): `tictoc::tic()` / `toc(quiet = TRUE)`, then
  `toc_out$toc - toc_out$tic`.
- SQL: `.timer on`; `run.sh` parses the `Run Time (s): real <seconds> ...`
  lines in query order.
- In the DuckDB variants, connection setup is **outside** the timed region in
  both languages: Python calls `get_con()` before `time.perf_counter()`, R
  calls `get_con()` before `tic()` and disconnects after `toc()`. Only the
  query plus materialization (`.pl()` in Python, `dbGetQuery()` in R) is timed.
  Preserve this split when adding benchmarks.

### Warmup

Before the timed benchmarks, Python's `main` runs a `warmup_set` whose results
are discarded (it currently warms up `read_all` and `read_all_duck`). The R
mirror reproduces this with its own `warmup_set` list, run via
`invisible(lapply(warmup_set, function(fn) fn()))`, before `benchmark_set`; R
warms up the same two entries (`read_all` and `read_all_duck`). Warmup entries
never appear in the CSV — only `benchmark_set` is written. When adding a
benchmark to Python's `benchmark_set`, consider whether it also belongs in
`warmup_set` and mirror that in R.

Both Python and R log each set before running it, labelling the warmup entries
as `(not recorded)` and the benchmark entries as `(recorded)` so the two are
never confused in the logs.

The DuckDB SQL mirror (`src/duck/bench.sql` / `run.sh`) has **no warmup**: the
`duckdb` CLI runs as a fresh process per benchmark run, so there is nothing to
keep warm across runs.

### Output format

Long CSV with columns `language,task,tool,elapsed`, appended to the file passed
as the first CLI argument (no header row). Language labels are `python`, `R`,
`sql`. Tool labels are:

| Language | Ground-truth tool | DuckDB tool |
|----------|-------------------|-------------|
| Python | `pyreadstat` | `duckdb` |
| R | `haven` | `duckdb` |
| SQL | — | `duckdb` |

All languages must emit the same task names; each language emits one row per
`(task, tool)` pair it supports. The DuckDB-based tool is labelled `duckdb` in
all clients, including the standalone SQL/extension benchmark.

## SQL specifics

There are three DuckDB surfaces to keep in sync:

1. The `*_duck` functions in `src/snake/bench.py` (agent-edited). They reuse
   `get_con()` to load the built extension and return `.pl()` results.
2. The `*_duck` functions in `src/RRR/bench.R` (agent-edited). They call
   `get_con()`, which connects with
   `DBI::dbConnect(duckdb::duckdb(config = list(allow_unsigned_extensions = "true"), shared_home = FALSE))`
   and runs `LOAD '<extension_path>'`; only the `DBI::dbGetQuery()` is timed.
   The `config` argument belongs on `duckdb::duckdb()`, **not** on
   `dbConnect()` — passing it to `dbConnect()` is silently ignored and `LOAD`
   then fails with "unsigned extensions are disabled by configuration".
3. `src/duck/bench.sql`, run by `src/bench/run.sh`, which owns the CSV writing.
   - Add one query per benchmark key, in `benchmark_set` order, each preceded
     by a comment naming the key.
   - `run.sh` extracts all `real` times with:
     ```bash
     mapfile -t duckdb_times < <(duckdb -unsigned < src/duck/bench.sql \
       | sed -nE 's/^Run Time \(s\): real ([0-9.]+) .*/\1/p')
     ```
   - Then writes one row per `(task, tool)` pair, e.g.:
     ```bash
     printf "%s,%s,%s,%s\n" sql read_all    duckdb "${duckdb_times[0]}" >> "$CSV"
     printf "%s,%s,%s,%s\n" sql read_subset duckdb "${duckdb_times[1]}" >> "$CSV"
     ```
   - When adding a benchmark, add its query to `bench.sql` **and** its
     `printf`/index line to `run.sh`. If SQL cannot express a benchmark,
     document the omission in both files.

## Current benchmark set

| Task | pyreadstat (ground truth) | Python `*_duck` | R haven | R `*_duck` | SQL (`duckdb`) |
|------|---------------------------|-----------------|---------|------------|-------------------|
| `read_all` | read every column | `SELECT * FROM read_stat(...)` | read every column | `SELECT * FROM read_stat(...)` | `FROM read_stat(...)` |
| `read_subset` | `usecols` / `columns_select` | `SELECT wage, person_id ...` | `col_select = columns_select` | `SELECT wage, person_id ...` | `SELECT wage, person_id FROM read_stat(...)` |

### Warmup sets

| Language | Warmup entries | Where |
|----------|----------------|-------|
| Python | `read_all`, `read_all_duck` | `warmup_set` in `main` (`src/snake/bench.py`) |
| R | `read_all`, `read_all_duck` | `warmup_set` in `main` (`src/RRR/bench.R`) |
| SQL | none | fresh `duckdb` CLI process per run |

## Notes

- Keep R's header comment and SQL comments describing behavior in sync with the
  actual code.
- The R DuckDB variant needs the `duckdb` and `DBI` R packages in addition to
  `haven` and `tictoc`. `make bench` runs the `renv` target before
  `src/bench/run.sh`, and `renv::init()` discovers dependencies from
  `src/RRR/bench.R`; run `renv::install(c("duckdb", "DBI"))` followed by
  `renv::snapshot()` (or just `make renv`) after changing R dependencies and
  commit the `renv.lock` change. The R `duckdb` package must bundle a DuckDB
  version compatible with the extension's `TARGET_DUCKDB_VERSION`
  (`duckdb-read-stat/Makefile`), otherwise `LOAD` fails; with DuckDB 1.5.x the
  R package version matches the DuckDB version (e.g. both `1.5.6`).
- `make bench` depends on the built extension and `data/test_small.sav`; see the
  `Makefile`.
