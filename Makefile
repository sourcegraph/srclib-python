ifeq ($(OS),Windows_NT)
# You can't change pip.exe being in use on Windows, so we'll copy original one and use it
       PIPCMD = cmd /C .env\\Scripts\\pip-vendored.exe --isolated --disable-pip-version-check
       MYPY = .env/Scripts/mypy
       ENV = virtualenv
else
       PIPCMD = .env/bin/pip
       MYPY = .env/bin/mypy
       ENV = virtualenv -p python3.5
endif

.PHONY: install test check

default: .env install test

.env:
	$(ENV) .env
ifeq ($(OS),Windows_NT)
	cp .env/Scripts/pip.exe .env/Scripts/pip-vendored.exe
endif

$(MYPY):
	$(PIPCMD) install mypy-lang

install-force: .env
	$(PIPCMD) install . --upgrade
	$(PIPCMD) install -r requirements.txt --upgrade

install: .env
	$(PIPCMD) install .
	$(PIPCMD) install -r requirements.txt

test: .env check
	srclib test

check: $(MYPY)
	$(MYPY) --silent-imports grapher
