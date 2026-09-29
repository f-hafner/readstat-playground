.PHONY: docker

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

duckdb-read-stat/build/debug/read_stat.duckdb_extension:
	make -C duckdb-read-stat configure
	make -C duckdb-read-stat debug

bench:	duckdb-read-stat/build/debug/read_stat.duckdb_extension
	mkdir -p results
	bash src/bench/run.sh results/bench.csv
