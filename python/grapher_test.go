// +build off
package python

import (
	"path/filepath"
	"reflect"
	"testing"

	"sourcegraph.com/sourcegraph/srclib/graph"
	"sourcegraph.com/sourcegraph/srclib/grapher2"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

func Test_GrapherTransform(t *testing.T) {
	p := defaultPythonEnv
	tests := []struct {
		TestName string
		Unit     unit.SourceUnit
		In       *rawGraphData
		Out      *grapher2.Output
		Err      error
	}{{
		TestName: "Well-formed input",
		Unit: &DistPackage{
			ProjectName:   "Pkg",
			RootDirectory: ".",
		},
		In: &rawGraphData{
			Graph: graphData_{
				Defs: []*pyDef{{
					Path: filepath.Join(srcRoot, "pkg/module1/class/method1"),
					File: filepath.Join(srcRoot, "pkg/module1.py"),
				}},
				Refs: []*pyRef{{
					Def:  filepath.Join(srcRoot, "pkg/module1/class/method1"),
					File: filepath.Join(srcRoot, "pkg/module2.py"),
				}, {
					Def:  filepath.Join(p.sitePackagesDir(), "dep1/module"),
					File: filepath.Join(srcRoot, "pkg/module1.py"),
				}},
				Docs: []*pyDoc{},
			},
			Reqs: []requirement{{
				ProjectName: "Dep1",
				RepoURL:     "g.com/o/dep1",
				Packages:    []string{"dep1"},
				Modules:     []string{},
			}},
		},
		Out: &grapher2.Output{
			Defs: []*graph.Def{{
				DefKey: graph.DefKey{
					Path:     "pkg/module1/class/method1",
					Unit:     "Pkg",
					UnitType: "PipPackage",
				},
				TreePath: "pkg/module1/class/method1",
				File:     "pkg/module1.py",
			}},
			Refs: []*graph.Ref{{
				DefUnitType: "PipPackage",
				DefUnit:     "Pkg",
				DefPath:     "pkg/module1/class/method1",
				UnitType:       "PipPackage",
				Unit:           "Pkg",
				File:           "pkg/module2.py",
			}, {
				DefRepo:     "g.com/o/dep1",
				DefUnitType: "PipPackage",
				DefUnit:     "Dep1",
				DefPath:     "dep1/module",
				UnitType:       "PipPackage",
				Unit:           "Pkg",
				File:           "pkg/module1.py",
			}},
		},
	}, {
		TestName: "Ignore requirement with no clone URL",
		Unit: &DistPackage{
			ProjectName:   "Pkg",
			RootDirectory: ".",
		},
		In: &rawGraphData{
			Graph: graphData_{
				Refs: []*pyRef{{
					Def:  filepath.Join(p.sitePackagesDir(), "dep1/module"),
					File: filepath.Join(srcRoot, "pkg/module1.py"),
				}},
				Docs: []*pyDoc{},
			},
			Reqs: []requirement{{
				ProjectName: "Dep1",
				RepoURL:     "", // empty clone URL
				Packages:    []string{"dep1"},
				Modules:     []string{},
			}},
		},
		Out: &grapher2.Output{},
	}}

	for _, test := range tests {
		out, err := p.grapherTransform(test.In, test.Unit)
		if test.Err != nil {
			if test.Err != err {
				t.Errorf("Expected error %v, but got %v", test.Err, err)
			}
		} else {
			if err != nil {
				t.Errorf("Unexpected error %v", err)
				continue
			}

			// normalize output
			if len(out.Docs) == 0 {
				out.Docs = nil
			}
			if len(out.Refs) == 0 {
				out.Refs = nil
			}
			if len(out.Defs) == 0 {
				out.Defs = nil
			}
			// Ignore data field
			for _, def := range out.Defs {
				def.Data = nil
			}

			if !reflect.DeepEqual(test.Out.Defs, out.Defs) {
				t.Errorf(`Test "%s": Expected output defs %+v but got %+v`, test.TestName, test.Out.Defs, out.Defs)
			}
			if !reflect.DeepEqual(test.Out.Refs, out.Refs) {
				var expRefs, actRefs []graph.Ref
				for _, ref := range test.Out.Refs {
					expRefs = append(expRefs, *ref)
				}
				for _, ref := range out.Refs {
					actRefs = append(actRefs, *ref)
				}
				t.Errorf(`Test "%s": Expected output references %#v but got %#v`, test.TestName, expRefs, actRefs)
			}
			if !reflect.DeepEqual(test.Out.Docs, out.Docs) {
				t.Errorf(`Test: "%s": Expected output docs %+v but got %+v`, test.TestName, test.Out.Docs, out.Docs)
			}

		}
	}
}
