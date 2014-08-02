// +build off
package python

import (
	"sourcegraph.com/sourcegraph/srclib/graph"
	"sourcegraph.com/sourcegraph/srclib/grapher"
	"sourcegraph.com/sourcegraph/srclib/repo"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

func Graph(unit *unit.SourceUnit) (*grapher.Output, error) {
	return &grapher.Output{
		Symbols: []*graph.Symbol{{
			SymbolKey: graph.SymbolKey{
				Repo:     repo.URI("github.com/foo/bar"),
				CommitID: "lskdfj",
				UnitType: "foo",
				Unit:     "bar",
				Path:     graph.SymbolPath("/bax/binky/"),
			}},
		},
		Refs: []*graph.Ref{},
		Docs: []*graph.Doc{},
	}, nil
}
