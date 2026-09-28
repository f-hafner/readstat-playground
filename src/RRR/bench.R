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


time_read <- function() {
  tic()
  df <- haven::read_sav(in_file)
  toc_out <- toc(quiet = TRUE)
  elapsed <- unname(toc_out$toc - toc_out$tic)
  log_info("read took %.4fs", elapsed)
  elapsed
}


main <- function(file_name) {
  log_info("language: R")
  benchmark_set <- list(
    read = time_read
  )
  log_info("running benchmarks: %s", paste(names(benchmark_set), collapse = ", "))
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
