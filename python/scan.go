package python

import (
	"sourcegraph.com/sourcegraph/srclib/repo"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

func Scan(repoRoot string) ([]*unit.SourceUnit, error) {
	return []*unit.SourceUnit{
		{
			Name: "fake-python",
			Type: "DistPackage",
			Repo: repo.URI("github.com/foo/bar"),
		},
	}, nil
}
