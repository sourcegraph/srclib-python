.PHONY: install install-docker

install:
	@mkdir -p .bin
	go build -o .bin/srclib-python
	sudo pip install -r requirements.txt --upgrade
	sudo pip install . --upgrade

install-docker:
	go install .
	sudo pip install -r requirements.txt --upgrade
	sudo pip install . --upgrade
	src toolchain build sourcegraph.com/sourcegraph/srclib-python
