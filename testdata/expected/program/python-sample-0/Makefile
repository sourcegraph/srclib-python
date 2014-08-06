.srclib-cache/aa9062406d5e5f029830a669177a1d91cded477d/python-sample-0/DistPackage.depresolve.json: .srclib-cache/aa9062406d5e5f029830a669177a1d91cded477d/python-sample-0/DistPackage.unit.v0.json
	src tool --methods program "sourcegraph.com/sourcegraph/srclib-python" "depresolve" < $^  1> $@

.srclib-cache/aa9062406d5e5f029830a669177a1d91cded477d/python-sample-0/DistPackage.graph.json: .srclib-cache/aa9062406d5e5f029830a669177a1d91cded477d/python-sample-0/DistPackage.unit.v0.json pkg0/__init__.py pkg0/m0.py pkg0/m1.py setup.py
	src tool --methods program "sourcegraph.com/sourcegraph/srclib-python" "graph" < $^ | src internal normalize-graph-data 1> $@

all: .srclib-cache/aa9062406d5e5f029830a669177a1d91cded477d/python-sample-0/DistPackage.depresolve.json .srclib-cache/aa9062406d5e5f029830a669177a1d91cded477d/python-sample-0/DistPackage.graph.json

.DELETE_ON_ERROR:
