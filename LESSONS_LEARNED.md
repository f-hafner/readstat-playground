
# Lessons learned: Dr. Duck

## General
- Stages of a DuckDB query and where extensions can hook into -> see Rusty Conover's slides
    - It's a callback-based system (?), and a specific example of how it 
    integrates with another library is here: https://github.com/f-hafner/duckdb-read-stat/pull/11#issuecomment-6443380329
- DuckDB's has some overhead compared to other tools. However, with our patches,
the DuckDB extension becomes competitive even at moderate file sizes. The exact
threshold is unclear though.
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
- Performance improvements in DuckDB might spill over into the extensions.
    - Example: async io is supported in DuckDB 2.0. Wider support requires that 
    it's added to the relevant APIs (C API), and then extensions need to upgrade.

## Specific to stat files
- See [ROADMAP].


## References
[ROADMAP]: ./ROADMAP.md


