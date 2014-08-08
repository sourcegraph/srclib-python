package python

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"

	"strings"

	"sourcegraph.com/sourcegraph/srclib/graph"
	"sourcegraph.com/sourcegraph/srclib/grapher"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

type GraphContext struct {
	Unit *unit.SourceUnit
	Reqs []*requirement
}

func NewGraphContext(unit *unit.SourceUnit) *GraphContext {
	var g GraphContext
	g.Unit = unit
	for _, dep := range unit.Dependencies {
		if req, err := asRequirement(dep); err == nil {
			g.Reqs = append(g.Reqs, req)
		}
	}
	return &g
}

// Graphs the Python source unit. If run outside of a Docker container, this assumes that the source unit has already
// been installed (via pip or `python setup.py install`).
func (c *GraphContext) Graph() (*grapher.Output, error) {
	if os.Getenv("IN_DOCKER_CONTAINER") != "" {
		// NOTE: this may cause an error when graphing any source unit that depends
		// on jedi (or any other dependency of the graph code)
		requirementFiles, err := filepath.Glob(filepath.Join(c.Unit.Dir, "*requirements.txt"))
		if err != nil {
			return nil, err
		}
		for _, requirementFile := range requirementFiles {
			exec.Command("pip", "install", "-r", requirementFile)
		}
		exec.Command("pip", "install", "-I", c.Unit.Dir)
	}

	cmd := exec.Command("python", "-m", "grapher.graph", c.Unit.Dir, "--verbose")
	cmd.Stderr = os.Stderr
	b, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var raw RawOutput
	if err := json.Unmarshal(b, &raw); err != nil {
		return nil, err
	}

	out := c.transform(&raw, c.Unit)
	return out, nil
}

func (c *GraphContext) transform(raw *RawOutput, unit *unit.SourceUnit) *grapher.Output {
	var out grapher.Output

	for _, def := range raw.Defs {
		out.Defs = append(out.Defs, c.transformDef(def))
		if doc := c.transformDefDoc(def); doc != nil {
			out.Docs = append(out.Docs, doc)
		}
	}
	for _, ref := range raw.Refs {
		if outRef, err := c.transformRef(ref); err == nil {
			out.Refs = append(out.Refs, outRef)
		} else {
			log.Printf("Could not transform ref %v: %s", ref, err)
		}
	}

	return &out
}

var jediKindToDefKind = map[string]graph.DefKind{
	"statement":        graph.Var,
	"statementelement": graph.Var,
	"param":            graph.Var,
	"module":           graph.Module,
	"submodule":        graph.Module,
	"class":            graph.Type,
	"function":         graph.Func,
	"lambda":           graph.Func,
	"import":           graph.Var,
}

func (c *GraphContext) transformDef(rawDef *RawDef) *graph.Def {
	return &graph.Def{
		DefKey: graph.DefKey{
			Repo:     c.Unit.Repo,
			Unit:     c.Unit.Name,
			UnitType: c.Unit.Type,
			Path:     graph.DefPath(rawDef.Path),
		},
		TreePath: graph.TreePath(rawDef.Path), // TODO: make this consistent w/ old way
		Kind:     jediKindToDefKind[rawDef.Kind],
		Name:     rawDef.Name,
		File:     rawDef.File,
		DefStart: rawDef.DefStart,
		DefEnd:   rawDef.DefEnd,
		Exported: rawDef.Exported,
		Data:     nil, // TODO
	}
}

func (c *GraphContext) transformRef(rawRef *RawRef) (*graph.Ref, error) {
	defUnit, err := c.inferSourceUnit(rawRef, c.Reqs)
	if err != nil {
		return nil, err
	}

	return &graph.Ref{
		DefRepo:     defUnit.Repo,
		DefUnitType: defUnit.Type,
		DefUnit:     defUnit.Name,
		DefPath:     graph.DefPath(rawRef.DefPath),

		Repo:     c.Unit.Repo,
		Unit:     c.Unit.Name,
		UnitType: c.Unit.Type,

		File:  rawRef.File,
		Start: rawRef.Start,
		End:   rawRef.End,
	}, nil
}

func (c *GraphContext) transformDefDoc(rawDef *RawDef) *graph.Doc {
	return nil
}

func (c *GraphContext) inferSourceUnit(rawRef *RawRef, reqs []*requirement) (*unit.SourceUnit, error) {
	if rawRef.ToBuiltin {
		return stdLibPkg.SourceUnit(), nil
	}
	return c.inferSourceUnitFromFile(rawRef.DefFile, reqs)
}

// Note: file is expected to be an absolute path
func (c *GraphContext) inferSourceUnitFromFile(file string, reqs []*requirement) (*unit.SourceUnit, error) {
	// Case: in current source unit (u)
	pwd, _ := os.Getwd()
	if isSubPath(pwd, file) {
		return c.Unit, nil
	}

	// Case: in dependent source unit(depUnits)
	fileCmps := strings.Split(file, string(filepath.Separator))
	pkgsDirIdx := -1
	for i, cmp := range fileCmps {
		if cmp == "site-packages" || cmp == "dist-packages" {
			pkgsDirIdx = i
			break
		}
	}
	if pkgsDirIdx != -1 {
		fileSubCmps := fileCmps[pkgsDirIdx+1:]
		fileSubPath := filepath.Join(fileSubCmps...)

		var foundReq *requirement = nil
	FindReq:
		for _, req := range reqs {
			for _, pkg := range req.Packages {
				if isSubPath(moduleToFilepath(pkg, true), fileSubPath) {
					foundReq = req
					break FindReq
				}
			}
			for _, mod := range req.Modules {
				if moduleToFilepath(mod, false) == fileSubPath {
					foundReq = req
					break FindReq
				}
			}
		}

		if foundReq == nil {
			var candidatesStr string
			if len(reqs) <= 7 {
				candidatesStr = fmt.Sprintf("%v", reqs)
			} else {
				candidatesStr = fmt.Sprintf("%v...", reqs[:7])
			}
			return nil, fmt.Errorf("Could not find requirement that contains file %s. Candidates were: %s",
				file, candidatesStr)
		}

		return foundReq.SourceUnit(), nil
	}

	// Case 3: in std lib
	pythonDirIdx := -1
	for i, cmp := range fileCmps {
		if strings.HasPrefix(cmp, "python") {
			pythonDirIdx = i
			break
		}
	}
	if pythonDirIdx != -1 {
		return stdLibPkg.SourceUnit(), nil
	}

	return nil, fmt.Errorf("Cannot infer source unit for file %s", file)
}

func isSubPath(parent, child string) bool {
	relpath, err := filepath.Rel(parent, child)
	return err == nil && !strings.HasPrefix(relpath, "..")
}

func moduleToFilepath(moduleName string, isPackage bool) string {
	moduleName = strings.Replace(moduleName, ".", "/", -1)
	if !isPackage {
		moduleName += ".py"
	}
	return moduleName
}

type RawOutput struct {
	Defs []*RawDef
	Refs []*RawRef
}

type RawDef struct {
	Path      string
	Kind      string
	Name      string
	File      string // relative path (to source unit directory)
	DefStart  int
	DefEnd    int
	Exported  bool
	Docstring string
	Data      interface{}
}

type RawRef struct {
	DefPath   string
	Def       bool
	DefFile   string // absolute path
	File      string // relative path (to source unit directory)
	Start     int
	End       int
	ToBuiltin bool
}
