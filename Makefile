.PHONY: install install-docker update-dockerfile

all: install update-dockerfile

install:
	@mkdir -p .bin
	go build -o .bin/srclib-python
	sudo pip install -r requirements.txt --upgrade
	sudo pip install . --upgrade

update-dockerfile:
	src toolchain build sourcegraph.com/sourcegraph/srclib-python

install-docker:
	go install .
	pip install -r requirements.txt --upgrade
	pip install . --upgrade
