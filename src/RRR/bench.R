#!/usr/bin/env Rscript
# Benchmark reading the cbs file with haven and DuckDB.
#
# Mirrors src/snake/bench.py: times haven::read_sav()/read_dta() and DuckDB
# queries over the read_stat() extension on data/cbs/file.<format> (or
# $IN_FILE) and writes the elapsed time to a CSV file passed as the first
# command line argument.
#
# Usage: Rscript bench.R <result_file> [sav|sav_row_compress|dta]
#
# Every task reads the whole file (there is no row limit). read_all_chunked is
# Python-only: it reads the file in slices with pyreadstat's row_offset, and
# haven has no equivalent, so it is omitted here. The same goes for
# read_all_parquet (reading the file and sinking it to parquet); see
# src/duck/bench.sql for the SQL omissions.
#
# Required packages (installed via renv, see Makefile):
#   haven, duckdb, DBI, tictoc
# The reason for the warmup is unexplored, but most likely
# similar to python: that the libraries import more libraries
# when they're called the first time.

library(haven)
library(tictoc)
library(DBI)
library(duckdb)

# haven reader per format. `sav` and `sav_row_compress` are both SPSS files,
# so they share haven::read_sav.
READERS <- list(
  sav = haven::read_sav,
  sav_row_compress = haven::read_sav,
  dta = haven::read_dta
)
FORMATS <- names(READERS)
# Dataset label written to the results csv (the files all live in data/cbs).
DATASET <- "cbs"
# Rows per fetched batch, mirroring DEFAULT_CHUNKSIZE in src/snake/readers.py.
CHUNKSIZE <- 500000

in_file <- "data/cbs/file.sav"
file_format <- "sav"
extension_path <- "duckdb-read-stat/build/release/read_stat.duckdb_extension"


resolve_in_file <- function(format) {
  # $IN_FILE takes precedence, matching src/snake/readers.py.
  env_file <- Sys.getenv("IN_FILE", unset = "")
  if (nzchar(env_file)) {
    return(env_file)
  }
  if (!format %in% FORMATS) {
    stop(
      sprintf("unknown format '%s'; choose from %s", format, paste(FORMATS, collapse = ", ")),
      call. = FALSE
    )
  }
  sprintf("data/cbs/file.%s", format)
}


# Mirrors pyreadstat_reader() in src/snake/readers.py.
reader <- function() READERS[[file_format]]


# Mirrors read_stat_call() in src/snake/readers.py: row-compressed SPSS files
# use a .sav_row_compress extension that the extension does not recognize, so
# the format has to be passed explicitly.
read_stat_call <- function() {
  if (file_format == "sav_row_compress") {
    sprintf("read_stat('%s', format = 'sav')", in_file)
  } else {
    sprintf("read_stat('%s')", in_file)
  }
}


# Mirrors get_con() in src/snake/readers.py: connection setup (including
# loading the extension) happens outside the timed region.
get_con <- function() {
  con <- DBI::dbConnect(
    duckdb::duckdb(
      config = list(allow_unsigned_extensions = "true"),
      # Use a temporary DuckDB home so connection setup does not touch a
      # shared ~/.duckdb or print storage notices while benchmarking.
      shared_home = FALSE
    )
  )
  DBI::dbExecute(con, sprintf("LOAD '%s'", extension_path))
  con
}


log_info <- function(fmt, ...) {
  # Mimic the python script's logging output:
  # "%(asctime)s %(levelname)s %(message)s"
  message(sprintf("%s INFO %s", format(Sys.time()), sprintf(fmt, ...)))
}


write_to_file <- function(benchmark_set, results, file_name) {
  # Append results in long format: language,task,tool,format,size,elapsed,branch.
  # The branch comes from $DUCKDB_READ_STAT_BRANCH, exported by src/bench/run.sh
  # so that all clients report the branch of the built extension.
  branch <- Sys.getenv("DUCKDB_READ_STAT_BRANCH", unset = "unknown")
  con <- file(file_name, open = "a")
  on.exit(close(con))
  for (i in seq_along(results)) {
    entry <- benchmark_set[[i]]
    writeLines(
      paste(
        c("R", entry$task, entry$tool, file_format, DATASET, results[[i]], branch),
        collapse = ","
      ),
      con
    )
  }
}


### ground truth: pyreadstat/haven - human edited
time_read_all <- function() {
  read_func <- reader()
  tic()
  df <- read_func(in_file)
  toc_out <- toc(quiet = TRUE)
  elapsed <- unname(toc_out$toc - toc_out$tic)
  log_info("read_all took %.4fs", elapsed)
  elapsed
}


### agent-edited: loading via duckdb
# Mirrors time_read_all_duckdb() in src/snake/bench.py: the connection is set
# up before timing starts, only the query (and its batched consumption) is
# timed. Rows are fetched CHUNKSIZE at a time and discarded so the full table
# is never materialized, matching read_all_duckdb() in src/snake/readers.py.
time_read_all_duck <- function() {
  con <- get_con()
  tic()
  res <- DBI::dbSendQuery(con, sprintf("SELECT * FROM %s", read_stat_call()))
  repeat {
    batch <- DBI::dbFetch(res, n = CHUNKSIZE)
    if (nrow(batch) == 0) break
  }
  DBI::dbClearResult(res)
  toc_out <- toc(quiet = TRUE)
  DBI::dbDisconnect(con, shutdown = TRUE)
  elapsed <- unname(toc_out$toc - toc_out$tic)
  log_info("read_all_duck took %.4fs", elapsed)
  elapsed
}


### warmup
# The whole file is read (there is no row limit anywhere), mirroring the
# warmup_set in src/snake/bench.py. Results are discarded.
warmup_read_all <- function() {
  read_func <- reader()
  invisible(read_func(in_file))
}


warmup_read_all_duck <- function() {
  con <- get_con()
  res <- DBI::dbSendQuery(con, sprintf("SELECT * FROM %s", read_stat_call()))
  repeat {
    batch <- DBI::dbFetch(res, n = CHUNKSIZE)
    if (nrow(batch) == 0) break
  }
  DBI::dbClearResult(res)
  DBI::dbDisconnect(con, shutdown = TRUE)
}


main <- function(file_name, format_arg = "sav") {
  in_file <<- resolve_in_file(format_arg)
  file_format <<- format_arg
  log_info("language: R")
  log_info("reading %s (format: %s)", in_file, file_format)
  # Warm up the readers by reading the whole file before timing, mirroring the
  # warmup_set in src/snake/bench.py. Results are discarded.
  warmup_set <- list(
    read_all = warmup_read_all,
    read_all_duck = warmup_read_all_duck
  )
  log_info("running warmup (not recorded): %s", paste(names(warmup_set), collapse = ", "))
  invisible(lapply(warmup_set, function(fn) fn()))
  # read_all_chunked is currently disabled (also commented out in Python) and
  # is Python-only (pyreadstat row_offset). read_all_parquet is Python-only.
  # Keep the order identical to Python's.
  benchmark_set <- list(
    list(task = "read_all", tool = "haven", fn = time_read_all),
    list(task = "read_all", tool = "duckdb", fn = time_read_all_duck)
  )
  benchmark_labels <- vapply(
    benchmark_set,
    function(entry) sprintf("%s (%s)", entry$task, entry$tool),
    character(1)
  )
  log_info("running benchmarks (recorded): %s", paste(benchmark_labels, collapse = ", "))
  results <- lapply(benchmark_set, function(entry) entry$fn())
  log_info("writing results to %s", file_name)
  write_to_file(benchmark_set, results, file_name)
}


if (sys.nframe() == 0) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) < 1) {
    stop(
      "Usage: Rscript bench.R <result_file> [sav|sav_row_compress|dta]",
      call. = FALSE
    )
  }
  format_arg <- if (length(args) >= 2) args[[2]] else "sav"
  main(args[[1]], format_arg)
}
