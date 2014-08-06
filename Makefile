.PHONY: install install-docker

install:
	@mkdir -p .bin
	go build -o .bin/srclib-python
	sudo pip install . --upgrade

install-docker:
	go install .
	sudo pip install . --upgrade

# TODO: virtualenv, pip
