.PHONY: docker

podman:
	podman build -t playground -f ./Dockerfile
	podman run -it --replace --name readstat -v $$(pwd):/src --network=host playground
