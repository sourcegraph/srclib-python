#!/usr/bin/env bash

ENV_URL_BASE="https://pypi.python.org/packages/source/v/virtualenv"
ENV_VERSION="13.1.0"

# By usign the pprint module, which is supported with the same syntax in python 2 and 3
# this python command can return the version as a single string for checking in bash.
if [ "$OS" = 'Windows_NT' ] ; then
	if [[ $(cmd /C python2.exe --version 2>&1) == $'Python 2'* ]] ; then
		PYTHON_BIN=python2.exe
	elif [[ "$(cmd /C python.exe --version 2>&1)" == $'Python 2'* ]] ; then
		PYTHON_BIN=python.exe
	else
        echo "Error: failed to locate a version of Python 2."
        echo "       \`srclib-python\` currently only works with Python 2."
        echo "       You should have python.exe or python2.exe in your PATH"
        exit 1
	fi    
elif [ "$(python -c 'from pprint import pprint; pprint(int(__import__("sys").version_info[:1][0]))')" = '2' ] ; then
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

if [ "$OS" = 'Windows_NT' ] ; then
	cmd /C $PYTHON_BIN virtualenv-$ENV_VERSION/virtualenv.py .env
else
	$PYTHON_BIN virtualenv-$ENV_VERSION/virtualenv.py .env
fi

# Cleanup.
rm virtualenv-$ENV_VERSION.tar.gz
rm -r virtualenv-$ENV_VERSION
