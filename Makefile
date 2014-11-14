.PHONY: install install-docker update-dockerfile

all: install update-dockerfile

install:
	@mkdir -p .bin
	go get -d ./...
	go build -o .bin/srclib-python
	sudo pip install -r requirements.txt --upgrade
	sudo pip install . --upgrade

test-dependencies:
	sudo pip install -r .test.requirements.txt --upgrade

update-dockerfile:
	src toolchain build sourcegraph.com/sourcegraph/srclib-python

install-docker:
	go install .
	pip install -r requirements.txt --upgrade
	pip install . --upgrade
