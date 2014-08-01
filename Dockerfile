FROM ubuntu:14.04

RUN apt-get update -qq
RUN apt-get install -qq curl git mercurial

# Install Go
RUN curl -Lo /tmp/golang.tgz https://storage.googleapis.com/golang/go1.3.linux-amd64.tar.gz
RUN tar -xzf /tmp/golang.tgz -C /usr/local
ENV GOROOT /usr/local/go
ENV GOBIN /usr/local/bin
ENV PATH /usr/local/go/bin:$PATH
ENV GOPATH /srclib

# Allow determining whether we're running in Docker
ENV IN_DOCKER_CONTAINER true

# Add this toolchain
ADD . /srclib/src/sourcegraph.com/sourcegraph/srclib-go/
WORKDIR /srclib/src/sourcegraph.com/sourcegraph/srclib-go
RUN go get -v -d
RUN go install

# Project source code is mounted at src
WORKDIR /src

ENTRYPOINT ["srclib-python"]
