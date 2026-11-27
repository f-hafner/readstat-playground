
# Readstat playground

Playing around with `readstat` libraries.

### Getting the source

- Fresh clone
  ```
  git clone --recurse-submodules git@github.com:f-hafner/readstat-playground.git
  ```

- Update an existing checkout
  ```
  cd readstat-playground/
  git submodule update --init --recursive
  ```

### Installation

On your normal system, you need to install uv, Python, and R.  If
duckdb is not available it is installed, but you can also install it
yourself.

Build the extension:
```bash
make build
```

### Features


#### Benchmarking 

Compare running time of queries in `haven`, `pyreadstat`, and `duckdb`.

```
make bench              # all formats, data/cbs/file.* (1M rows)
make bench dta          # a single format
make scaling            # growing files in data/scaling/ (100k, 1m, 10m)
make plot               # draw all plots into results/figs/
```

Benchmark timing results are recorded in `results/bench.csv` and
`results/bench_scaling.csv`; every row also records the `duckdb-read-stat`
branch the extension was built from. Subsequent runs append to the datasets.

The benchmark records the current branch of the vendored `duckdb-read-stat` extension
(but you need to re-build manually after switching branches).
Currently supported branches:
- `develop` -- no changes compared to the upstream extension
- `pull-reader-proto` -- patches a pull-based API into `ReadStat`, allowing the
extension to keep the reader open
- `parallel-proto` -- on top of `pull-reader-proto`, adds ability for multithreading,
by building a row index for file formats that do not support random seeks in `O(1)`.
Multithreading is only useful where it's not bottlenecked (for instance, batch
processing in Python is in single batches); the task for reading the file
and writing to a parquet file is the only one that illustrates the potential of 
parallelisation.

#### Design considerations

**Lower bound for speed gains of DuckDB**

The core benchmark in bench.py is designed to be a lower bound on 
the benefits of DuckDB versus the other clients.
- The file is smaller than the largest registry files, in terms of rows
(1M vs $\geq$ 17M) as well in columns (30 vs 100) and types (numeric only vs mixed
numeric and strings).
- At this size, files can be read into memory. This means that pyreadstat/haven
can read the file at once, without repeatedly seeking.
- For out-of-memory file sizes, pyreadstat/haven need chunking, while
the pull-reader in DuckDB handles this without repeated opening/closing.
- Additionally, for file formats that do not support random seeks in `O(1)`, chunking
gets increasingly slower with file size -- which is documented through the `bench_scaling.py`
benchmark.
- Because a pull API in ReadStat would allow other tools to also avoid the 
repeated seeking, the current advantage of DuckDB for out-of-memory files may fade away
eventually.

**Tasks are as comparable as possible**
- The extension is not feature-complete in terms of value conversion and 
handling of missing data.
- To make results as comparable as possible across tools, the input data
are as simple as possible - no missings, only numerics.


See details in [src/bench/README.md](`src/bench/README.md`)

#### Running native `readstat` features

For exploring `readstat`:
- skipping columns; see details in [src/native/skip-columns/README.md](`src/native/skip-columns/README.md`)


# Useful docs
- Unofficial documentation of the `.sav` file format: https://www.gnu.org/software/pspp/pspp-dev/html_node/System-File-Format.html
- Reverse-engineered SAS7BDAT specification: https://github.com/tk3369/SASLib.jl/blob/master/SAS7BDAT.md
