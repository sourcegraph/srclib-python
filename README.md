# srclib-python [![Build Status](https://travis-ci.org/sourcegraph/srclib-python.png?branch=master)](https://travis-ci.org/sourcegraph/srclib-python)

## Jedi

**srclib-python** is a [srclib](https://sourcegraph.com/sourcegraph/srclib)
toolchain that performs Python code analysis: type checking, documentation
generation, jump-to-definition, dependency resolution, etc.

It enables this functionality in any client application whose code analysis is
powered by srclib, including [Sourcegraph.com](https://sourcegraph.com).

## Installation

This toolchain is not a standalone program; it provides additional functionality
to applications that use [srclib](https://srclib.org).

First,
[install the `srclib` program (see srclib installation instructions)](https://srclib.org/gettingstarted/).

Installing `srclib` should automatically install `srclib-python`.

To verify that installation succeeded, run:

```
srclib toolchain list
```

You should see this srclib-python toolchain in the list.

Now that this toolchain is installed, any program that relies on srclib will support Python.


## Known issues

srclib-python is alpha-quality software. It powers code analysis on
[Sourcegraph.com](https://sourcegraph.com) but has not been widely tested or
adapted for other use cases.

It also expects projects to follow best practices such as including a `setup.py` file. It doesn't currently handle
decorators or namespace packages correctly.

There also seems to be a problem with some function parameter type detection.

srclib-python runs on Python 2.7 (and some glue code in Go), but it can still process Python 3 libraries.


## Misc

srclib-python's type analysis is based on
[Jedi](https://github.com/davidhalter/jedi).
