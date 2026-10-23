test_data := data/test_small.sav data/test_small.dta

DUCKDB 		:= $(shell command -v duckdb 2> /dev/null)
DUCKDB_VERSION	:= $(shell sed -nE 's/TARGET_DUCKDB_VERSION=v([0-9]+\.[0-9]+\.[0-9]+)/\1/p' duckdb-read-stat/Makefile)

define INSTALL_DUCKDB
if [ -z "$(DUCKDB)" ]; then \
	echo "DuckDB not found, installing ..."; \
	curl https://install.duckdb.org | DUCKDB_VERSION=$(DUCKDB_VERSION) bash; \
fi
endef


.PHONY: bench build install-duckdb clean-renv native native/skip-columns

bench:	duckdb-read-stat/build/debug/read_stat.duckdb_extension data/test_small.sav install-duckdb renv
	mkdir -p results
	bash src/bench/run.sh results/bench.csv

build: duckdb-read-stat/build/debug/read_stat.duckdb_extension

duckdb-read-stat/build/debug/read_stat.duckdb_extension:
	make -C duckdb-read-stat configure
	make -C duckdb-read-stat debug

install-duckdb:
	@$(call INSTALL_DUCKDB)

native: native/skip-columns 

duckdb-read-stat/configure/platform.txt:
	make -C duckdb-read-stat configure

duckdb-read-stat/build/debug/libread_stat.so: duckdb-read-stat/configure/platform.txt
	make -C duckdb-read-stat debug

native/skip-columns: duckdb-read-stat/build/debug/libread_stat.so data/test_small.dta
	cmake -S src/native/skip-columns -B src/native/skip-columns/build
	cmake --build src/native/skip-columns/build

$(test_data): data/test_small.%:
	mkdir -p data
	uv run src/snake/create_stat_file.py --format $* 10000 -o $@

renv:
	Rscript -e 'd <- Sys.getenv("R_LIBS_USER"); dir.create(d, recursive = TRUE, showWarnings = FALSE); install.packages("renv", lib = d, repos = "https://cloud.r-project.org")'
	Rscript -e 'renv::init()' # creates renv/ + .Rprofile + renv.lock
	Rscript -e 'renv::restore()' 
clean-renv:
	rm -rf renv .Rprofile
