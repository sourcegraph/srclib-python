ifeq ($(OS),Windows_NT)
       PIPCMD = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
# You can't change pip.exe being in use on Windows, so we'll copy original one and use it
       COPYPIPCMD = cmd /C .env\\Scripts\\pip-vendored.exe --isolated --disable-pip-version-check
       ENV = virtualenv
else
       PIPCMD = .env/bin/pip
       COPYPIPCMD = $(PIPCMD)
       ENV = virtualenv -p python3.5
endif

.PHONY: install test check

default: .env install test

.env:
	$(ENV) .env
ifeq ($(OS),Windows_NT)
	cp .env/Scripts/pip.exe .env/Scripts/pip-vendored.exe
endif

.env/bin/mypy:
	$(PIPCMD) install mypy-lang

install-force: .env
	$(PIPCMD) install . --upgrade
	$(COPYPIPCMD) install -r requirements.txt --upgrade

install: .env
	$(PIPCMD) install .
	$(COPYPIPCMD) install -r requirements.txt

test: .env check
	srclib test

check: .env/bin/mypy
	.env/bin/mypy --silent-imports grapher
