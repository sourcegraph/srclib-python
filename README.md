# srclib-python [![Build Status](https://travis-ci.org/sourcegraph/srclib-python.png?branch=master)](https://travis-ci.org/sourcegraph/srclib-python)

## Jedi

**srclib-python** is a [srclib](https://sourcegraph.com/sourcegraph/srclib)
toolchain that performs Python code analysis: type checking, documentation
generation, jump-to-definition, dependency resolution, etc.

It enables this functionality in any client application whose code analysis is
powered by srclib, including:

* [emacs-sourcegraph-mode](https://sourcegraph.com/sourcegraph/emacs-sourcegraph-mode),
  an editor plugin for Emacs
* [Sourcegraph.com](https://sourcegraph.com), an open-source code search engine

## Installation

This toolchain is not a standalone program; it provides additional functionality
to editor plugins and other applications that use [srclib](https://srclib.org).

First,
[install the `src` program (see srclib installation instructions)](https://srclib.org/gettingstarted/).

Installing `src` should automatically install `srclib-python`.

To verify that installation succeeded, run:

```
src toolchain list
```

You should see this srclib-python toolchain in the list.

Now that this toolchain is installed, any program that relies on srclib (such as
editor plugins) will support Python.


## Usage

Most people use `srclib` (and by extension `srclib-python`) via an [editor plugin](https://srclib.org/plugins/emacs/) or
via [Sourcegraph](https://sourcegraph.com/). You can also use `srclib-python` on the command line using the [`src` command](https://srclib.org/api/overview/).

## Known issues

srclib-python is alpha-quality software. It powers code analysis on
[Sourcegraph.com](https://sourcegraph.com) but has not been widely tested or
adapted for other use cases.

It also expects projects to follow best practices such as including a `setup.py` file. It doesn't currently handle
decorators or namespace packages correctly.

There also seems to be a problem with some function parameter type detection.

srclib-python runs on Python 2.7 (and some glue code in Go), but it can still process Python 3 libraries.


## Tests

Testing this toolchain requires that you have installed `src` from
[srclib](https://sourcegraph.com/sourcegraph/srclib) and that you have this
toolchain set up. See srclib documentation for more information.

To test this toolchain's output against the expected output, run:

```
# build the Docker container to run the tests in isolation
src toolchain build sourcegraph.com/sourcegraph/srclib-python

# run the tests
src test
```

By default, that command runs tests in an isolated Docker container. To run the
tests on your local machine, run `src test -m program`. See the srclib
documentation for more information about the differences between these two
execution methods.

## TODO

Add screenshots



## Contributing

Patches are welcomed via GitHub pull request! See
[CONTRIBUTING.md](./CONTRIBUTING.md) for more information.

srclib-python's type analysis is based on
[Jedi](https://github.com/davidhalter/jedi).
