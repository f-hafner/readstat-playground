# Benchmark inputs live in two directories, both generated on demand:
#   data/cbs/file.<format>                    1M-row files for `make bench`
#   data/scaling/test_<size>.sav_row_compress files for `make scaling`
#
# Commands:
#   make bench [sav|sav_row_compress|dta]  run the cbs benchmark (all formats
#                                          unless a format goal is given)
#   make scaling [SIZES="100k 1m"]         run the scaling benchmark
#   make plot                              draw all plots from both CSVs
#   make build                             (re)build the read_stat extension
#   make clean                             remove results/
#
# Overridable variables:
#   BENCH_REPEATS    how many times `make bench` runs the whole benchmark (default 1)
#   SCALING_REPEATS  measurements per size/tool for `make scaling` (default 5)
#   SIZES            scaling sizes to benchmark (default "100k 1m 10m")
FORMATS := sav sav_row_compress dta
SIZES ?= 100k 1m 10m
BENCH_REPEATS ?= 1
SCALING_REPEATS ?= 5

DATA_DIR := data/cbs
SCALING_DIR := data/scaling
RESULTS := results
EXTENSION := duckdb-read-stat/build/release/read_stat.duckdb_extension

# The branch of the duckdb-read-stat submodule, recorded in every result row
# so that `make plot` can show/compare branches (plots show all by default).
BRANCH := $(shell git -C duckdb-read-stat rev-parse --abbrev-ref HEAD)
export DUCKDB_READ_STAT_BRANCH := $(BRANCH)

_format := $(filter $(FORMATS),$(MAKECMDGOALS))
OUT_FORMATS ?= $(if $(_format),$(_format),$(FORMATS))

.PHONY: bench scaling plot build clean renv $(FORMATS)

bench: $(EXTENSION) renv $(addprefix $(DATA_DIR)/file.,$(OUT_FORMATS))
	mkdir -p $(RESULTS)
	set -e; for i in $$(seq $(BENCH_REPEATS)); do \
		echo "bench run $$i/$(BENCH_REPEATS)"; \
		bash src/bench/run.sh $(RESULTS)/bench.csv "$(OUT_FORMATS)"; \
	done

scaling: $(EXTENSION) $(addprefix $(SCALING_DIR)/test_,$(addsuffix .sav_row_compress,$(SIZES)))
	mkdir -p $(RESULTS)
	uv run src/snake/bench_scaling.py $(RESULTS)/bench_scaling.csv \
		--sizes $(SIZES) \
		--data-dir $(SCALING_DIR) \
		--repeats $(SCALING_REPEATS)

plot:
	@test -f $(RESULTS)/bench.csv || { echo "missing $(RESULTS)/bench.csv; run 'make bench' first" >&2; exit 1; }
	@test -f $(RESULTS)/bench_scaling.csv || { echo "missing $(RESULTS)/bench_scaling.csv; run 'make scaling' first" >&2; exit 1; }
	uv run src/snake/plot_bench.py $(RESULTS)/bench.csv -o $(RESULTS)/figs
	uv run src/snake/plot_scaling.py $(RESULTS)/bench_scaling.csv -o $(RESULTS)/figs

# Aliases so `make bench [sav|sav_row_compress|dta]` selects the formats
# (read from MAKECMDGOALS above).
$(FORMATS): bench

build: $(EXTENSION)

$(EXTENSION):
	make -C duckdb-read-stat configure
	make -C duckdb-read-stat release

renv:
	@test -f renv.lock || { \
		Rscript -e 'd <- Sys.getenv("R_LIBS_USER"); dir.create(d, recursive = TRUE, showWarnings = FALSE); install.packages("renv", lib = d, repos = "https://cloud.r-project.org")'; \
		Rscript -e 'renv::init()'; \
		Rscript -e 'renv::restore()'; \
	}

$(DATA_DIR)/file.%: src/snake/create_stat_file.py
	mkdir -p $(DATA_DIR)
	uv run src/snake/create_stat_file.py --format $* -o $@

$(SCALING_DIR)/test_%.sav_row_compress: src/snake/create_scaling_stat_file.py
	mkdir -p $(SCALING_DIR)
	uv run src/snake/create_scaling_stat_file.py --sizes $* --outdir $(SCALING_DIR)

clean:
	rm -rf $(RESULTS)
