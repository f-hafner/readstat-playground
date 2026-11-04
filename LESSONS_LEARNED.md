
# Lessons learned: Dr. Duck

## General
- Stages of a DuckDB query and where extensions can hook into -> see Rusty Conover's slides
- DuckDB has a file system API; in the C API, has become stable as of v1.5.6
    - Used under the hood for reading from S3 etc
    - Extensions can also use it for doing file system operations
- Memory management
    - DuckDB has its own API for allocating and deallocating memory, 
    and extensions should use that 
    (as much as possible?). AFAIU, it counts towards DuckDB's memory 
    limit that the user can set. 
    - What would happen if an extension did not use duckdb's memory allocation? 
    At least, it'd circumvent the limit and more likely OOM instead of
    using DuckDB disk-spilling.

## Specific to stat files
- See [ROADMAP].


## References
[ROADMAP]: ./ROADMAP.md


