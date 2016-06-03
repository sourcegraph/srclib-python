ifeq ($(OS),Windows_NT)
       PIP = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
else
       PIP = .env/bin/pip
endif

ifeq ($(OS),Windows_NT)
       PIP27 = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
else
       PIP27 = .env27/bin/pip
endif


.PHONY: install test check virtualenvs

default: virtualenvs install test

virtualenvs: .env .env27

.env27:
	virtualenv -p python2.7 .env27

.env:
	virtualenv -p python3.5 .env

.env/bin/mypy:
	$(PIP) install mypy-lang

install-force: virtualenvs
	$(PIP) install . --upgrade
	$(PIP) install -r requirements.txt --upgrade
	$(PIP27) install . --upgrade
	$(PIP27) install -r requirements.txt --upgrade

install: virtualenvs
	$(PIP27) install .
	$(PIP27) install -r requirements.txt

test: virtualenvs check
	srclib test

check: .env/bin/mypy
	.env/bin/mypy --silent-imports grapher
