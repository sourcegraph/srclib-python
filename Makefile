ifeq ($(OS),Windows_NT)
# You can't change pip.exe being in use on Windows, so we'll copy original one and use it
       PIPCMD = cmd /C .env\\Scripts\\pip-vendored.exe --isolated --disable-pip-version-check
       PIP2CMD = cmd /C .env\\Scripts\\pip-vendored.exe --isolated --disable-pip-version-check
       ENV = virtualenv
       ENV2 = virtualenv
       MYPY = .env/Scripts/mypy
else
       PIPCMD = .env/bin/pip3.5
       PIP2CMD = .env/bin/pip2.7
       ENV = virtualenv -p python3.5
       ENV2 = virtualenv -p python2.7
       MYPY = .env/bin/mypy
endif

.PHONY: install test check

default: .env install test

.env:
	$(ENV2) .env
	$(ENV) .env
ifeq ($(OS),Windows_NT)
	cp .env/Scripts/pip.exe .env/Scripts/pip-vendored.exe
endif

$(MYPY):
	$(PIPCMD) install mypy-lang

install-force: .env
	$(PIPCMD) install . --upgrade
	$(PIPCMD) install -r requirements.txt --upgrade
	$(PIP2CMD) install . --upgrade
	$(PIP2CMD) install -r requirements.txt --upgrade

install: .env
	$(PIPCMD) install .
	$(PIPCMD) install -r requirements.txt
	$(PIP2CMD) install .
	$(PIP2CMD) install -r requirements.txt

test: .env check
	srclib test

check: $(MYPY)
	$(MYPY) --silent-imports grapher
