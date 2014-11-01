.PHONY: install install-docker update-dockerfile

all: install update-dockerfile

install:
	@mkdir -p .bin
	go get -d ./...
	go build -o .bin/srclib-python
	pip install -r requirements.txt --upgrade --user
	pip install . --upgrade --user

test-dependencies:
	pip install -r .test.requirements.txt --upgrade --user

update-dockerfile:
	src toolchain build sourcegraph.com/sourcegraph/srclib-python

install-docker:
	go install .
	pip install -r requirements.txt --upgrade --user
	pip install . --upgrade --user
