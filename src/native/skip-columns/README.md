# skip-columns

`main.c` is a small test program that parses a Stata `.dta` file with
[readstat](../../../duckdb-read-stat/third_party/readstat) and prints
rows as tab-separated values, skipping the variables declared in `main.c`.
It links against `libread_stat.so`, which is built by the
`duckdb-read-stat` extension.

## Prerequisites

Build the extension first so that
`duckdb-read-stat/build/debug/libread_stat.so` exists:

```bash
# from the repository root
make build
```

## Build

From the repository root:

```bash
make native/skip-columns
```

Manually (after building `duckdb-read-stat`):
```bash
cd src/native/skip-columns
cmake -B build 
cmake --build build
```


## Run

From repo root:

```bash
./src/native/skip-columns/build/skip-columns data/test_small.dta
```
