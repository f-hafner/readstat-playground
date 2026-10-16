
## Benchmarking

Run intermediate steps individually:

- Create test file
  ```
  make data/test_small.sav
  make data/test_small.dta
  ```

- Create the R environment
  ```
  make renv
  ```

- Remove the current R environment
  ```
  make clean-renv
  ```

- Build the extension
  ```
  make build
  ```


#### Reading in the `sas7bdat` file
- All libraries support reading from this format. The `trial_data.sas7bdat` file
has 1M rows with 3 columns.
- For the full file, Python and R took around 1sec while duckdb took 3.2s

Taken together:
- duckdb opens/reads file in each of the 2048-sized chunks
- According to the github issue, pyreadstat with chunking would lead to a similar
result
- Somehow this speed disadvantage of the duckdb extension is much more visible
for the SAS file; for SPSS file, pyreadstat and duckdb are on par. Does this
suggest that, avoiding repeated file opening, would make even SPSS reads
much faster in duckdb?


### Projection pushdown / selecting columns
- The Python and R libraries support selecting columns; it makes reads faster, suggesting
some sort of projection pushdown.
    - In R, reading 1/3 columns of the sas file takes around 1/3 of the time. Reading the
    sav file has smaller speedup.
    - For pyreadstat, `usecols` leads also to faster execution
- In contrast, in DuckDB, the timing does not differ between
`select a, b from read_stat` and `from read_stat`.
    - In one case, the full takes 2.8s and 2 columns takes 2.7s.
