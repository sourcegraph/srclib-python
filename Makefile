ifeq ($(OS),Windows_NT)
       PIP = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
       ENV = virtualenv
else
       PIP = .env/bin/pip
       ENV = virtualenv -p python3.5
endif

.PHONY: install test check

default: .env install test

.env:
	$(ENV) .env

.env/bin/mypy:
	$(PIP) install mypy-lang

install-force: .env
	$(PIP) install . --upgrade
	$(PIP) install -r requirements.txt --upgrade

install: .env
	$(PIP) install .
	$(PIP) install -r requirements.txt

test: .env check
	go test $(shell go list ./... | grep -v /vendor/)
	srclib test

check: .env/bin/mypy
	.env/bin/mypy --silent-imports grapher
