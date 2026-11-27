---
name: sync-bench
description: Keep the pyreadstat benchmark ground truth in sync with the agent-maintained DuckDB SQL approach in src/snake/readers.py and src/snake/bench.py, plus the R (haven + DuckDB) and DuckDB SQL benchmark scripts. Use when the pyreadstat read functions in src/snake/readers.py or the timers in src/snake/bench.py change, or when editing the duckdb readers in src/snake/readers.py, src/RRR/bench.R, src/duck/bench.sql, or src/bench/run.sh.
---

# Sync benchmarks with the pyreadstat ground truth

The read functions live in **`src/snake/readers.py`**; the benchmark timers
live in **`src/snake/bench.py`**. Inside both files the **pyreadstat functions
are the ground truth** (sections marked `### ground truth: pyreadstat - human
edited`). The agent-maintained DuckDB functions (`get_con`, `read_stat_call`,
`read_all_duckdb`, `time_read_all_duckdb`), the R mirror (both its haven and
DuckDB variants), and the DuckDB SQL mirror must all be updated whenever the
pyreadstat ground truth changes.

> Note: the DuckDB SQL approach lives in **three** places: the `*_duckdb`
> functions in `src/snake/readers.py` / `src/snake/bench.py` (agent-edited),
> the `*_duck` functions in `src/RRR/bench.R` (via the R `duckdb` package), and
> `src/duck/bench.sql`. All are agent-maintained mirrors of the pyreadstat
> ground truth and must be kept in sync.

## Files

| Role | Path |
|------|------|
| Ground truth (pyreadstat, human-edited) | `src/snake/readers.py` — `read_all_pyreadstat`, `read_all_pyreadstat_chunked`, `number_of_rows`, `pyreadstat_reader`; `src/snake/bench.py` — `### ground truth: pyreadstat - human edited` section |
| Agent-maintained DuckDB mirror (Python) | `src/snake/readers.py` — `get_con`, `read_stat_call`, `read_all_duckdb`; `src/snake/bench.py` — `### agent-edited: loading via duckdb` section |
| R mirror (haven + DuckDB) | `src/RRR/bench.R` |
| DuckDB SQL mirror | `src/duck/bench.sql` |
| Runner / labeler | `src/bench/run.sh` |

## Procedure

1. Find out what changed in the **pyreadstat ground truth**, in this order:
   ```bash
   git diff src/snake/readers.py src/snake/bench.py          # uncommitted
   git show HEAD -- src/snake/readers.py src/snake/bench.py  # committed
   ```
   Focus on the `### ground truth: pyreadstat - human edited` sections and the
   `read_all_pyreadstat*` functions; ignore changes to the DuckDB sections
   (those are yours to regenerate).
   If neither shows a meaningful change to the pyreadstat benchmark set (e.g.
   the commit only touched unrelated files or the output is not informative),
   **ask the user** what changed instead of guessing.
2. Identify the changed/added/removed **pyreadstat functions** and the
   `(task, tool)` entries in `benchmark_set`.
3. Update the agent-maintained mirrors to match:
   - the DuckDB reader in `src/snake/readers.py` and its timer in
     `src/snake/bench.py` (one per pyreadstat benchmark, added to
     `benchmark_set` after the pyreadstat block),
   - the warmup sets in `src/snake/bench.py` and `src/RRR/bench.R` (see
     [Warmup](#warmup)),
   - the R mirror `src/RRR/bench.R`, which has both a haven and a DuckDB
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

- The pyreadstat ground truth defines `time_<task>()`; the agent mirror defines
  `time_<task>_duckdb()` (e.g. `time_read_all` → `time_read_all_duckdb`). R
  defines `time_<task>` for the haven variant and `time_<task>_duck` for the
  DuckDB variant.
- Python's `benchmark_set` is keyed by `(task, tool)` tuples, where `task` is
  the canonical task name (`read_all`, `read_all_chunked`, `read_all_parquet`)
  and `tool` is the implementation label (`pyreadstat`, `duckdb`).
  `read_all_chunked` is currently **disabled** (commented out in Python);
  `read_all` and `read_all_parquet` are active. Current order:
  `(read_all, pyreadstat)`, `(read_all, duckdb)`,
  `(read_all_parquet, pyreadstat)`, `(read_all_parquet, duckdb)`. Every task
  reads the whole file: there is **no row limit** (`LIMIT`, `row_limit`, or
  `n_max`) in any client.
- R's `benchmark_set` is a list of entries of the form
  `list(task = ..., tool = ..., fn = ...)`. Use the same `task` labels as
  Python and keep the order identical; the R tools are `haven` (ground truth)
  and `duckdb`.
- SQL rows in `run.sh` use the same task names (without the `_duckdb` suffix)
  and the tool label `duckdb`, matching the DuckDB tool label used by the
  Python and R clients.
- Keep ordering consistent: R's `benchmark_set` order must match Python's
  exactly, and SQL query order must match the pyreadstat entries in that same
  order.

### Reading the file

- Input path: `src/snake/readers.py` resolves `data/cbs/file.<file_format>` via
  `resolve_in_file(file_format)` (`$IN_FILE` takes precedence). `bench.py`
  takes the file format as its second CLI argument; R mirrors this with
  `resolve_in_file()` and the same CLI argument; SQL uses the `@@IN_FILE@@` and
  `@@FORMAT_PARAM@@` placeholders that `src/bench/run.sh` substitutes. `run.sh`
  loops over formats, setting `data/cbs/file.<format>` for each.
  Formats are `sav`, `sav_row_compress`, and `dta`; `make bench dta`
  benchmarks only `dta`, and `make bench` benchmarks all three.
- Extension path (DuckDB): Python's `get_con()` and R's `get_con()` both load
  `duckdb-read-stat/build/release/read_stat.duckdb_extension` via a relative
  path (`EXTENSION_PATH` in `readers.py`, `extension_path` in R); SQL loads it
  with `LOAD` at the top of the script.
- Full read: Python `read_all_pyreadstat(in_file, file_format)` dispatches on
  `pyreadstat_reader()`, which maps every format explicitly through the
  `READERS` dict (`sav` and `sav_row_compress` → `pyreadstat.read_sav`, `dta` →
  `pyreadstat.read_dta`) with `output_format="polars"`; the Python DuckDB
  mirror `read_all_duckdb(con, in_file, file_format, n_rows, chunksize)` pulls
  the query result as Arrow record batches
  (`fetch_record_batch(rows_per_batch=chunksize)`) and discards each one; R
  haven `reader()(in_file)` where `reader()` looks the format up in its own
  `READERS` list (`haven::read_sav` / `haven::read_dta`); R DuckDB
  `dbSendQuery()` + repeated `dbFetch(res, n = CHUNKSIZE)` (discarded) +
  `dbClearResult()`; SQL `FROM read_stat('@@IN_FILE@@'@@FORMAT_PARAM@@)`.
- Row count: `number_of_rows()` (`metadataonly=True`, in `src/snake/readers.py`)
  is called by `bench.py`'s `main` **before** the warmup/timed sets and passed
  to the readers as `n_rows`. Metadata discovery therefore never counts as
  benchmark work; it is used for the chunk offsets and the progress-bar total.
- Progress bars: the Python readers wrap their batch loops in `tqdm`
  (`disable=None`, so bars disappear when stderr is not a TTY). R and SQL have
  no progress bar yet.
- The readers read and discard the data, mimicking a job that would write each
  batch to parquet (only the read is timed). Exception: `pyreadstat_frame()`
  returns the polars frame, which `read_all_pyreadstat()` discards and the
  parquet sink writes. The DuckDB readers consume batches rather than
  materializing the result, so they use as little memory as the chunked
  pyreadstat reader.
  Python's `DEFAULT_CHUNKSIZE` and R's `CHUNKSIZE` (both in
  `src/snake/readers.py` and `src/RRR/bench.R`) must stay equal.
- Chunked read: `read_all_pyreadstat_chunked(in_file, file_format, n_rows,
  chunksize)` chunks **manually**, not with `pyreadstat.read_file_in_chunks()`.
  It reads one `row_offset`/`row_limit` slice per chunk, discarding each chunk
  (a real job would write it to parquet). This task is Python-only; the
  omission in R and SQL is intentional and must stay documented in
  `src/RRR/bench.R`, `src/duck/bench.sql`, and `src/bench/run.sh`.
- Full read: every client reads the **whole** file, which has 1M rows
  (`N_OBS` in `src/snake/create_stat_file.py`). pyreadstat materializes a
  polars frame and discards it; DuckDB streams Arrow record batches
  (`read_all_duckdb`); R reads with haven (`read_func(in_file)`) and with a
  `dbFetch(n = CHUNKSIZE)` loop; SQL simply runs `FROM read_stat(...)`.
- Read + parquet sink (Python-only): reads the whole file and writes it to
  parquet. pyreadstat writes the polars frame with
  `pyarrow.parquet.ParquetWriter`; DuckDB uses
  `COPY (SELECT * FROM read_stat(...)) TO '<dir>'
  (FORMAT parquet, PER_THREAD_OUTPUT true)` so each thread writes its own file.
  That only happens on a connection opened with `get_con(parallel=True)`, which
  runs `SET preserve_insertion_order=false`: with the default (ordered) config
  DuckDB funnels the copy through one ordered sink and writes a single file at
  ~100% CPU. Only `time_read_all_parquet_duckdb` passes `parallel=True`; every
  other task keeps insertion order so row order still matches the source file
  (needed by `verify_readers.py` and by chunk-by-chunk comparisons).
  `bench.py` writes into a `tempfile.TemporaryDirectory` opened around the
  benchmark run, so the outputs are deleted when the session ends. There is no
  R or SQL mirror (intentional; keep the omission documented in
  `src/RRR/bench.R`, `src/duck/bench.sql`, and `src/bench/run.sh`).
- Format override: `sav_row_compress` files use a `.sav_row_compress`
  extension that the extension does not recognize, so `read_stat_call()` and
  the SQL mirror pass `format = 'sav'` for it (`@@FORMAT_PARAM@@` is that
  clause or an empty string). `sav` and `dta` are inferred from the extension.

### Timing

- Python (both pyreadstat and `*_duckdb`): `time.perf_counter()`.
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
are discarded. Because there is no row limit anywhere, the warmup also reads
the whole file (`read_all_pyreadstat()`, `read_all_duckdb()`), which triggers
the lazy polars/pyarrow imports. The R mirror reproduces this with its own
`warmup_set` list (`read_all`, `read_all_duck`), run via
`invisible(lapply(warmup_set, function(fn) fn()))`, before `benchmark_set`.
Warmup entries never appear in the CSV — only `benchmark_set` is written.
When adding a benchmark to Python's `benchmark_set`, consider whether it also
needs a warmup and mirror that in R.

Both Python and R log each set before running it, labelling the warmup entries
as `(not recorded)` and the benchmark entries as `(recorded)` so the two are
never confused in the logs.

The DuckDB SQL mirror (`src/duck/bench.sql` / `run.sh`) has **no warmup**: the
`duckdb` CLI runs as a fresh process per benchmark run, so there is nothing to
keep warm across runs.

### Output format

Long CSV with columns `language,task,tool,format,size,elapsed,branch`,
appended to the file passed as the first CLI argument (no header row). Language
labels are `python`, `R`, `sql`. The `size` column holds the dataset label
`cbs` (all files live in `data/cbs`). The `branch` column records the
`duckdb-read-stat` submodule branch the extension was built from: it comes from
`extension_branch()` in `readers.py`, which honours `$DUCKDB_READ_STAT_BRANCH`;
`make` and `src/bench/run.sh` export that variable so `bench.py`, `bench.R`,
and the SQL rows all agree. Scaling rows (`src/snake/bench_scaling.py`) carry
the same column. `src/snake/plot_bench.py` splits runs on `RUN_START`, which
must stay the first row `bench.py` writes (currently `read_all` /
`pyreadstat`); update it if the first `benchmark_set` entry changes. Tool labels
are:

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

1. The DuckDB readers in `src/snake/readers.py` (agent-edited). `get_con()`
   loads the built extension, `read_stat_call()` builds the `read_stat()`
   expression, and `read_all_duckdb()` consumes the result as Arrow batches
   (`fetch_record_batch`) and discards them, so the full table is never
   materialized. `time_read_all_duckdb()` in `bench.py` calls `get_con()`
   before timing.
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
   - `run.sh` substitutes the `@@IN_FILE@@` and `@@FORMAT_PARAM@@` placeholders
     (the format parameter is `, format = 'sav'` for `sav_row_compress`), then
     extracts all `real` times with:
     ```bash
     mapfile -t duckdb_times < <(sed \
       -e "s|@@IN_FILE@@|${IN_FILE}|g" \
       -e "s|@@FORMAT_PARAM@@|${FORMAT_PARAM}|g" \
       src/duck/bench.sql \
       | duckdb -unsigned \
       | sed -nE 's/^Run Time \(s\): real ([0-9.]+) .*/\1/p')
     ```
   - Then writes one row per `(task, tool)` pair, including format, size, and
     branch (indices follow the order of the queries in `bench.sql`; only
     `read_all` is active right now):
     ```bash
     printf "%s,%s,%s,%s,%s,%s,%s\n" sql read_all duckdb "$FORMAT" "$SIZE" "${duckdb_times[0]}" "$BRANCH" >> "$CSV"
     ```
   - `run.sh` loops over the selected formats (default: all of `sav`,
     `sav_row_compress`, `dta`), exports `IN_FILE`, `FORMAT`, and `SIZE`, and
     passes the format as the CLI argument to the Python and R clients.
   - When adding a benchmark, add its query to `bench.sql` **and** its
     `printf`/index line to `run.sh`. If SQL cannot express a benchmark,
     document the omission in both files.

## Current benchmark set

| Task | pyreadstat (ground truth) | Python `duckdb` | R haven | R `duckdb` | SQL (`duckdb`) |
|------|---------------------------|-----------------|---------|------------|-------------------|
| `read_all` | read every column of the whole file | `fetch_record_batch(rows_per_batch=DEFAULT_CHUNKSIZE)`, discarded | read every column | `dbFetch(n = CHUNKSIZE)` loop, discarded | `FROM read_stat(...)` |
| `read_all_parquet` | whole file written with `ParquetWriter` | `COPY ... TO '<dir>'` with `PER_THREAD_OUTPUT` | — | — | — |
| `read_all_chunked` *(disabled)* | manual `row_offset`/`row_limit` slices with `chunksize=300_000` | — | — (no haven equivalent) | — | — (no SQL equivalent) |

The `read_all`/`read_all_chunked` batch loops (kept in the codebase) show a
`tqdm` bar; the totals come from the `n_rows` argument that `bench.py` discovers
with `number_of_rows()` before timing starts. The R `read_all` duckdb loop
fetches `CHUNKSIZE` rows at a time for the same memory reason, and R has no
progress bar.

`read_all_parquet` is Python-only, and `read_all_chunked` has no R/SQL
equivalent; both omissions must stay documented in `src/RRR/bench.R`,
`src/duck/bench.sql`, and `src/bench/run.sh`. Apart from those, R's
`benchmark_set` mirrors Python's active order and contents (currently the two
`read_all` tasks), and commented-out entries must match across clients too.

### Warmup sets

| Language | Warmup entries | Where |
|----------|----------------|-------|
| Python | `read_all`, `read_all_duckdb` (whole file) | `warmup_set` in `main` (`src/snake/bench.py`) |
| R | `read_all`, `read_all_duck` (whole file) | `warmup_set` in `main` (`src/RRR/bench.R`) |
| SQL | none | fresh `duckdb` CLI process per run |

## Notes

- `src/snake/verify_readers.py` compares pyreadstat and DuckDB output chunk
  by chunk (`--chunks`, `--chunksize`, default format `sav`) and exits non-zero
  on differences. It reads the same `data/cbs/file.<format>` and applies the
  same `sav_row_compress` format override, so keep it in sync when the read
  path changes.
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
- The Makefile has a small set of goals: `make bench [sav|sav_row_compress|dta]`
  (cbs files in `data/cbs/`, generated by `src/snake/create_stat_file.py`,
  1M rows, 30 numeric columns; `BENCH_REPEATS=N` repeats the whole run, and
  the append-only CSV plus `plot_bench.py`'s run detection average over them),
  `make scaling` (files in `data/scaling/`,
  generated by `src/snake/create_scaling_stat_file.py`; default sizes
  `100k 1m 10m`, with `50m` opt-in via `SIZES="... 50m"`), `make plot` (runs
  `plot_bench.py` (`mean_timing.png`, `duckdb_speedup.png`) and
  `plot_scaling.py` into `results/figs/`; DuckDB results are split per branch,
  native results are pooled across branches), `make build`
  (rebuild the extension), and `make clean` (remove `results/`). There is no
  SAS target: `sas7bdat` fixtures cannot be generated on this machine.
  `bench_scaling.py` still accepts `--format sas7bdat` for files generated
  elsewhere. Both plot scripts show all branches by default (`--branch`
  restricts the figure to one); `plot_scaling.py` always drops the
  `parallel-proto` branch (that benchmark only covers the pull-reader
  extension). DuckDB results are split per branch, native results are pooled
  across branches.
