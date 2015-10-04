FROM ubuntu:14.04

# Install make, Python development headers and other libs that some libraries require to install on Ubuntu.
RUN apt-get update -qq && apt-get install -qq curl git mercurial make python-dev libxslt1-dev libxml2-dev zlib1g-dev

# Install Go
RUN curl -Lo /tmp/golang.tgz https://storage.googleapis.com/golang/go1.4.2.linux-amd64.tar.gz && \
    tar -xzf /tmp/golang.tgz -C /usr/local

ENV GOROOT /usr/local/go
ENV GOBIN /usr/local/bin
ENV PATH /usr/local/go/bin:$PATH
ENV GOPATH /srclib

# Install Python and pip and create virtualenv.
RUN curl https://raw.githubusercontent.com/pypa/pip/7.0.3/contrib/get-pip.py | python && \
    pip install virtualenv && \
    virtualenv /venv

ENV PATH /venv/bin:$PATH

# Allow determining whether we're running in Docker
ENV IN_DOCKER_CONTAINER true

# Add this toolchain
ADD . /srclib/src/sourcegraph.com/sourcegraph/srclib-python/
WORKDIR /srclib/src/sourcegraph.com/sourcegraph/srclib-python
RUN go get -v -d
RUN make install-docker

# Add srclib (unprivileged) user
RUN useradd -ms /bin/bash srclib && \
    mkdir /src && \
    chown -R srclib /src /srclib /venv

USER srclib

# Project source code is mounted at src
WORKDIR /src

ENTRYPOINT ["srclib-python"]
