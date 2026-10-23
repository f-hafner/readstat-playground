
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
make bench
```

Benchmark timing results are recorded in `results/bench.csv`.
Subsequent runs append to the dataset.  

See details in [src/bench/README.md](`src/bench/README.md`)

#### Running native `readstat` features

For exploring `readstat`:
- skipping columns; see details in [src/native/skip-columns/README.md](`src/native/skip-columns/README.md`)


# Useful docs
- Unofficial documentation of the `.sav` file format: https://www.gnu.org/software/pspp/pspp-dev/html_node/System-File-Format.html
