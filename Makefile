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
