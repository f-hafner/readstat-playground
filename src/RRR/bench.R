#!/usr/bin/env Rscript
# Benchmark reading an SPSS file with haven and DuckDB.
#
# Mirrors src/snake/bench.py: times haven::read_sav() and DuckDB queries over
# the read_stat() extension on data/test_small.sav and writes the elapsed time
# to a CSV file passed as the first command line argument.
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

in_file <- "data/test_small.sav"
columns_select <- c("wage", "person_id")
extension_path <- "duckdb-read-stat/build/debug/read_stat.duckdb_extension"


# Mirrors get_con() in src/snake/bench.py: connection setup (including loading
# the extension) happens outside the timed region.
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


write_to_file <- function(results, file_name) {
  # Append results in long format.
  con <- file(file_name, open = "a")
  on.exit(close(con))
  for (task in names(results)) {
    writeLines(paste(c("R", task, results[[task]]), collapse = ","), con)
  }
}


time_read_all <- function() {
  tic()
  df <- haven::read_sav(in_file)
  toc_out <- toc(quiet = TRUE)
  elapsed <- unname(toc_out$toc - toc_out$tic)
  log_info("read_all took %.4fs", elapsed)
  elapsed
}


time_read_subset <- function() {
  tic()
  df <- haven::read_sav(in_file, col_select = c("wage", "person_id"))
  toc_out <- toc(quiet = TRUE)
  elapsed <- unname(toc_out$toc - toc_out$tic)
  log_info("read_subset took %.4fs", elapsed)
  elapsed
}


# Mirrors the *_duck functions in src/snake/bench.py: the connection is set up
# before timing starts, only the query (and its materialization) is timed.
time_read_all_duck <- function() {
  con <- get_con()
  tic()
  df <- DBI::dbGetQuery(con, sprintf("SELECT * FROM read_stat('%s')", in_file))
  toc_out <- toc(quiet = TRUE)
  DBI::dbDisconnect(con, shutdown = TRUE)
  elapsed <- unname(toc_out$toc - toc_out$tic)
  log_info("read_all_duck took %.4fs", elapsed)
  elapsed
}


time_read_subset_duck <- function() {
  con <- get_con()
  tic()
  query <- sprintf(
    "SELECT %s FROM read_stat('%s')",
    paste(columns_select, collapse = ", "),
    in_file
  )
  df <- DBI::dbGetQuery(con, query)
  toc_out <- toc(quiet = TRUE)
  DBI::dbDisconnect(con, shutdown = TRUE)
  elapsed <- unname(toc_out$toc - toc_out$tic)
  log_info("read_subset_duck took %.4fs", elapsed)
  elapsed
}


main <- function(file_name) {
  log_info("language: R")
  # Warm up the readers before timing, mirroring the warmup_set in
  # src/snake/bench.py. Results are discarded.
  warmup_set <- list(
    read_all = time_read_all,
    read_all_duck = time_read_all_duck
  )
  log_info("running warmup (not recorded): %s", paste(names(warmup_set), collapse = ", "))
  invisible(lapply(warmup_set, function(fn) fn()))
  benchmark_set <- list(
    read_all = time_read_all,
    read_subset = time_read_subset,
    read_all_duck = time_read_all_duck,
    read_subset_duck = time_read_subset_duck
  )
  log_info("running benchmarks (recorded): %s", paste(names(benchmark_set), collapse = ", "))
  results <- lapply(benchmark_set, function(fn) fn())
  log_info("writing results to %s", file_name)
  write_to_file(results, file_name)
}


if (sys.nframe() == 0) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) < 1) {
    stop("Usage: Rscript bench.R <result_file>", call. = FALSE)
  }
  main(args[[1]])
}
