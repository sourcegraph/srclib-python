#!/usr/bin/env bash

ENV_URL_BASE="https://pypi.python.org/packages/source/v/virtualenv"
ENV_VERSION="13.1.0"

# Try to use `python2`, otherwise use `python`.
PYTHON_BIN=$(which python2)
if ! [ -x "$PYTHON_BIN" ]; then
    PYTHON_BIN=$(which python);
    if ! [ -x "$PYTHON_BIN" ]; then
            echo "Error: failed to locate python executable."
            exit 1
    fi
fi

# Check if we have Python 2.
PYTHON_VERSION=$($PYTHON_BIN --version 2>&1)
# Python 2.7.10
#        ^ - 7th char.
if [ "${PYTHON_VERSION:7:1}" != '2' ] ; then
    echo "Error: failed to locate Python2."
    echo "       \`srclib-python\` currently only works with Python 2."
    exit 2
fi

# Setup virtual env.
curl -O $ENV_URL_BASE/virtualenv-$ENV_VERSION.tar.gz
tar xzf virtualenv-$ENV_VERSION.tar.gz
$PYTHON_BIN virtualenv-$ENV_VERSION/virtualenv.py .env

# Cleanup.
rm virtualenv-$ENV_VERSION.tar.gz
rm -r virtualenv-$ENV_VERSION
