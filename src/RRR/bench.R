#!/usr/bin/env Rscript
# Benchmark reading an SPSS file with haven.
#
# Mirrors src/snake/bench.py: times haven::read_sav() on data/test.sav and
# writes the elapsed time to a CSV file passed as the first command line
# argument.
#
# Required packages (installed in the container, see Dockerfile):
#   haven, tictoc

library(haven)
library(tictoc)

in_file <- "data/test_small.sav"


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


main <- function(file_name) {
  log_info("language: R")
  # Warm up the reader before timing, mirroring the warmup_set in
  # src/snake/bench.py. Results are discarded.
  warmup_set <- list(
    read_all = time_read_all
  )
  log_info("running warmup (not recorded): %s", paste(names(warmup_set), collapse = ", "))
  invisible(lapply(warmup_set, function(fn) fn()))
  benchmark_set <- list(
    read_all = time_read_all,
    read_subset = time_read_subset
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
