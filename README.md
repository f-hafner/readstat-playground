
# Readstat playground

Playing around with `readstat` libraries.

### Installation

```bash
make
```

To connect to a running podman instance (and use htop):
```bash
podman exec -it readstat bash
```

### Usage

1. Create test file 

Inside the container:
```
uv run src/create_stat_file.py 1_000 -o test.sav
```

2. Read test file

**`R`**

```R
library(haven)
df = read_sav("test.sav")
summary(df)
head(df)
```

**`python`**

```bash
uv run --with "pyreadstat,pandas" python
```

```python
import pyreadstat
df, meta = pyreadstat.read_sav("test.sav")
df.head()
df.describe() # note the difference to R
```

**`DuckDB`**
```sql
INSTALL read_stat FROM community;
LOAD read_stat;
FROM read_stat('test.sav'); 
-- NULLs are correct; categorical labels not converted
CREATE TABLE mytab as (FROM read_stat('test.sav'));
```


### Timing execution

```bash
uv run src/create_stat_file.py 10_000_000 -o test.sav

uv run --with "ipython,pyreadstat,pandas" ipython
```

```python
import pyreadstat
%timeit df, meta = pyreadstat.read_sav("test.sav")
```

```R
library(haven)
library(tictoc)

tic()
read_sav("test.sav")
toc()
```

Timings (10M obs)
- python pyreadstat: 29s
- duckdb: 25.7s. (1 vs 4 threads takes same amount of time.)
- R haven: 86s


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

### Key question: why not use `create teable from read_stat`, pay the cost once, and then work directly with the table?
- (this is similar to just converting to a parquet file and then working with this)
- analytics/analysis (`ggsql`?) on large files with 100s of columns and millions of rows (INPATAB) in limited memory 
environment? -> then, the scan-once and query-later amortization workflow may also become more valuable?
- From the DANS [reuse manual](https://dans.knaw.nl/en/reuse-data-manual/)
    >For many file types, our Data Stations provide a viewer which lets you have a look at the data directly: you can read text documents, consult tabular data, and play audio/video files within the Data Station. 
    - We could ask them if there's big demand for interactively exploring datasets in stat formats
- Chat suggested more use cases; in general, "extension shines for exploration, constraint, and freshness", parquet shines for repetition
    - ad-hoc inspection of files that may never be ingested
    - storage/quota-constrained environments (no room for a copy; larger than RAM)
    - source keeps changing/derived copies are a liability - cache-invalidation problem
    -> this is what happens in CBS; it's a problem as long as CBS does not change their
    deliveries to parquet. 
    - More generally, this extension can be a bridge between
    legacy SAS/SPSS-based systems and a duckdb data stack.

### Ideas for a workplan

A goal could be feature completeness to libraries in Python and R:
- Avoid repeatedly opening the file, which seems to be a problem especially for
SAS files. See github issue.
- Support reading categoricals correctly; check other metadata from pyreadstat
and if they're read correctly.
- Support projection pushdown
    - `from read_stat()` takes as long as `select date, wage from read_stat`. 
      -> can projection pushdown be implemented with read_stat? 
        - see this function in duckdb: https://duckdb.org/docs/lts/clients/c/table_functions#duckdb_table_function_supports_projection_pushdown
        - not found in source code of duckdb read stat
        - see also `duckdb_init_get_column_count` and `duckdb_init_get_column_index` functions in duckdb
        - sqlite_scanner reference for projection pushdown: https://github.com/duckdb/duckdb-sqlite/blob/13119c01097c8030c09caab7f7f476967e0bd2db/src/sqlite_scanner.cpp#L436

Further ideas
- Claude:
    - >.sav: rows are stored as a stateful compressed stream (bytecode/zlib compression, variable-width    
       records) with no row index and no resync points. To know where row N starts, you must decode rows   
       0..N-1. 
- Explore two-pass trick: one sequential pass for indexing, and parallel decoding? The other libraries
have not implemented this, and I don't consider it a priority at the moment.
- (Profile to confirm the above conjectures and maybe for memory profiling?)

Todo / other questions
- try .dta? .dat?
- why has the extension moved to the unstable C API?

 ### Assessment from GLM 5.3:
 1. Resolve governance: extension maintenance status, why unstable C API, maintainer appetite for      
    contributions.                                                                                     
 2. Profile the chunking hypothesis (cheap, decisive).                                                 
 3. Categorical/value-label correctness + metadata exposure (highest user value, matches your stated   
    use cases).                                                                                        
 4. Avoid re-opening / streaming fix for SAS (validated by #2).                                        
 5. Projection pushdown (only if the format structure permits).                                        
 6. Parallel decoding / two-pass indexing — later.                                                     
                                                                                                       
 Verdict: the reasoning justifies exploring contribution, but the document currently conflates         
 hypotheses (chunking overhead, SPSS speedup potential) with findings (timing numbers). Two cheap      
 experiments — profiling the extension, and checking maintainer/project health — would turn "probably  
 worth contributing" into a confident decision, and would reorder the feature list toward              
 correctness-first (labels/metadata) rather than performance-first.   

