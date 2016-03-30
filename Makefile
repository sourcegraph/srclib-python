ifeq ($(OS),Windows_NT)
	EXE = .bin/srclib-python.exe
	PIP = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
else
	EXE = .bin/srclib-python
	PIP = .env/bin/pip
endif

.PHONY: install

default: govendor .env install

.env:
	bash ./install_env.sh

$(EXE): $(shell /usr/bin/find . -type f -name '*.go')
	@mkdir -p .bin
	go build -o $(EXE)

install: $(EXE)
	$(PIP) install -r requirements.txt --upgrade
	$(PIP) install . --upgrade

govendor:
	go get github.com/kardianos/govendor
	govendor sync
