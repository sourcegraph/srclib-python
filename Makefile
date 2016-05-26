ifeq ($(OS),Windows_NT)
       PIP = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
else
       PIP = .env/bin/pip
endif

.PHONY: install

default: .env install test

.env:
	virtualenv -p python3.5 .env

.env/bin/mypy:
	$(PIP) install mypy-lang

install-force: .env
	$(PIP) install . --upgrade
	$(PIP) install -r requirements.txt --upgrade

install: .env
	$(PIP) install .
	$(PIP) install -r requirements.txt

test: .env .env/bin/mypy
	.env/bin/mypy --silent-imports grapher
	srclib test
