ifeq ($(OS),Windows_NT)
	EXE = .bin/srclib-python.exe
	PIP = cmd /C .env\\Scripts\\pip.exe --isolated --disable-pip-version-check
else
	EXE = .bin/srclib-python
	PIP = .env/bin/pip
endif

.PHONY: install docker-image release

.env:
	bash ./install_env.sh

$(EXE): $(shell /usr/bin/find . -type f -name '*.go')
	@mkdir -p .bin
	go get -d ./...
	go build -o $(EXE)

install: .env $(EXE)
	$(PIP) install -r requirements.txt --upgrade
	$(PIP) install . --upgrade

docker-image:
	docker build -t srclib/srclib-python .

release: docker-image
	docker push srclib/srclib-python
