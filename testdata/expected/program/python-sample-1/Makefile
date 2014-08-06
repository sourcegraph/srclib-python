.srclib-cache/02f4d67459ca62624086a48d0b4e69631d049646/python-sample-1/DistPackage.depresolve.json: .srclib-cache/02f4d67459ca62624086a48d0b4e69631d049646/python-sample-1/DistPackage.unit.v0.json
	src tool --methods program "sourcegraph.com/sourcegraph/srclib-python" "depresolve" < $^  1> $@

.srclib-cache/02f4d67459ca62624086a48d0b4e69631d049646/python-sample-1/DistPackage.graph.json: .srclib-cache/02f4d67459ca62624086a48d0b4e69631d049646/python-sample-1/DistPackage.unit.v0.json app/__init__.py app/app.py setup.py
	src tool --methods program "sourcegraph.com/sourcegraph/srclib-python" "graph" < $^ | src internal normalize-graph-data 1> $@

all: .srclib-cache/02f4d67459ca62624086a48d0b4e69631d049646/python-sample-1/DistPackage.depresolve.json .srclib-cache/02f4d67459ca62624086a48d0b4e69631d049646/python-sample-1/DistPackage.graph.json

.DELETE_ON_ERROR:
