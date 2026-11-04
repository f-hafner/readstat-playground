
# Roadmap: Use cases & feature development for duckdb-read-stat


## Use cases: mostly around fast I/O for stat file formats
- Tabular data ingest in dataverse could *potentially* be done by DuckDB
    - Will need more research and understanding of the existing stack
- Reading large stat files, for instance for registry data (NL, DK)
    - At least in NL, in the secure environment the data are stored on a 
    network file system. Thus, network latency *may* be a factor too, and async IO might eventually
    become interesting (though this needs more research and is currently
    not available in the client APIs AFAIK). See also [async IO in duckdb].
- Small interactive queries via tabular viewer GUIs (for humans), CLI (for humans and agents)
    - For tabular viewer: load readstat file into a duckdb table and 
    use existing tools (check)
    - For CLI: works already out of the box, but unless it's just exploring
    metdata/table `head`s, better to also load it into a duckdb table

## Proposed stages for the remainder of the project


I think we may just go ahead on our own dev branch and think about
merging into upstream later. The benefit is that we can go at our own pace;
the cost is that the features may not get merged during this project.

Proposed steps:
1. Upgrade to the (unstable) DuckDB 2.0.0 C API
2. Fix some small memory leaks
3. Merge the PR on column projection
4. Focus on making loading of stat files as fast as possible


### Loading stat files as fast as possible: details

#### Motivation
- My hunch is that this is the key value proposition of using DuckDB
versus existing tools (`haven`, `pyreadstat`). Thus, fixing this is 
the biggest lever in driving adoption.
- Feature parity to existing tools is also important, but (i) worthless
if reading is slow and (ii) easier to do.
- It seems to me that making I/O fast could also be interesting from 
an engineering perspective.


#### Facts
- Even on small `spss` files, duckdb-read-stat is currently a bit slower
than `pyreadstat`
    - Presumed reason: small overhead from re-setting the readstat parser
    and seeking into the position of the next-to-read row between
    duckdb data chunks.
    - I think, since `duckdb-read-stat` now uses duckdb's file system
    API for opening the file which is persisted across data chunks,
    there is no cost for reading/opening file across data chunks, but I 
    should confirm this.
- On large `sas7bdat` files, duckdb is substantially slower than `haven`,
see [speed on SAS files].
    - Presumed reason: on this file format, it seems readstat does not expose
    random seeks, see [seeking on SAS files].
    - As a result, in `duckdb-read-stat`, each data chunk currently scans the
    entire file until the chunk to be read, leading to quadratic time complexity.
- By default, both `haven` and `pyreadstat` read the whole file in one go. 
    - On one hand, duckdb's chunking approach makes `duckdb-read-stat`
    amenable to large files that do support random seeks. 
        - `pyreadstat` supports reading file in chunks by repeatedly opening, seeking, and closing the file,
          which is probably slower than duckdb but I have not checked.
        - Unclear if `haven` supports chunking.
    - On the other hand, the quadratic time complexity makes it very slow
    for file formats that do not support it.

#### Development steps

1. Implement pull-based approach for sas files with a linear scan, following
discussion in [speed on SAS files]. 
    - Separate parsers for metadata, variables, and values.
    - Persist the state of the sas parser
    - TBD: precise implementation for non-sas files.
2. Explore support for multithreaded reads (might be a stretch during existing project).
    - Note: I don't fully understand this, but I think duckdb supports
    multithreaded reads in other formats, see [async IO in duckdb]
    - For sas files, it will require an auxiliary index for random seeks,
    so that individual threads can read from different positions in the file.
    The index could be built during the bind, or during the global init. 
    - TBD: What is necessary for other file formats?



## References

[speed on SAS files]: https://github.com/dylanmeysmans/duckdb-read-stat/issues/3
[seeking on SAS files]: https://github.com/WizardMac/ReadStat/issues/317
[async IO in duckdb]: https://duckdb.org/2026/07/31/asynchronous-io
- I used Deepseek-4.1-flash for researching this topic and understanding the
existing code base.
- The present file is hand-written.
