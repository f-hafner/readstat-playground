test_data := data/test_small.sav data/test_small.dta

.PHONY: podman build renv bench

podman:
	podman build -t playground -f ./Dockerfile
	mkdir -p results
	podman run -it --replace --name readstat \
		--userns=keep-id \
		-v $$(pwd)/src:/home/ubuntu/src \
		-v $$(pwd)/data:/home/ubuntu/data \
		-v $$(pwd)/results:/home/ubuntu/results \
		-w /home/ubuntu/ \
		--network=host playground

$(test_data): data/test_small.%:
	mkdir -p data
	uv run src/snake/create_stat_file.py --format $* 10000 -o $@

build: duckdb-read-stat/build/debug/read_stat.duckdb_extension

duckdb-read-stat/build/debug/read_stat.duckdb_extension:
	make -C duckdb-read-stat configure
	make -C duckdb-read-stat debug

renv:
	Rscript -e 'd <- Sys.getenv("R_LIBS_USER"); dir.create(d, recursive = TRUE, showWarnings = FALSE); install.packages("renv", lib = d, repos = "https://cloud.r-project.org")'
	Rscript -e 'renv::init()' # creates renv/ + .Rprofile + renv.lock

bench:	duckdb-read-stat/build/debug/read_stat.duckdb_extension renv data/test_small.sav
	mkdir -p results
	bash src/bench/run.sh results/bench.csv
