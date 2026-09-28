.PHONY: docker

podman:
	podman build -t playground -f ./Dockerfile
	mkdir -p results
	podman run -it --replace --name readstat \
		-v $$(pwd)/src:/project/src \
		-v $$(pwd)/data:/project/data \
		-v $$(pwd)/results:/project/results \
		-w /project \
		--network=host playground
