ifeq ($(IN_DOCKER_CONTAINER),true)
	PIP = pip
else ifeq ($(OS),Windows_NT)
	EXE = .bin/srclib-python.exe
	PIP = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
else
	EXE = .bin/srclib-python
	PIP = .env/bin/pip
endif

.PHONY: install install-docker update-dockerfile

all: install update-dockerfile

.env:
	bash ./install_env.sh

$(EXE): $(shell /usr/bin/find . -type f -name '*.go')
	@mkdir -p .bin
	go get -d ./...
	go build -o $(EXE)

install: .env $(EXE)
	$(PIP) install -r requirements.txt --upgrade
	$(PIP) install . --upgrade

update-dockerfile:
	src toolchain build sourcegraph.com/sourcegraph/srclib-python

install-docker: .env
	go install .
	$(PIP) install -r requirements.txt --upgrade
	$(PIP) install . --upgrade
