#!/usr/bin/env bash

ENV_URL_BASE="https://pypi.python.org/packages/source/v/virtualenv"
ENV_VERSION="13.1.0"

# By usign the pprint module, which is supported with the same syntax in python 2 and 3
# this python command can return the version as a single string for checking in bash.
if [ "$(python -c 'from pprint import pprint; pprint(int(__import__("sys").version_info[:1][0]))')" = '2' ] ; then
    PYTHON_BIN=$(which python)
elif [ "$(python2 -c 'from pprint import pprint; pprint(int(__import__("sys").version_info[:1][0]))')" = '2' ] ; then
    PYTHON_BIN=$(which python2)
else
    echo "Error: failed to locate a version of Python 2."
    echo "       \`srclib-python\` currently only works with Python 2."
    exit 1
fi

# Setup virtual env.
curl -O $ENV_URL_BASE/virtualenv-$ENV_VERSION.tar.gz
tar xzf virtualenv-$ENV_VERSION.tar.gz
$PYTHON_BIN virtualenv-$ENV_VERSION/virtualenv.py .env

# Cleanup.
rm virtualenv-$ENV_VERSION.tar.gz
rm -r virtualenv-$ENV_VERSION
