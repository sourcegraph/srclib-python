// +build off

package python

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"text/template"

	"sourcegraph.com/sourcegraph/srclib/config"
	"sourcegraph.com/sourcegraph/srclib/container"
	"sourcegraph.com/sourcegraph/srclib/graph"
	"sourcegraph.com/sourcegraph/srclib/grapher2"
	"sourcegraph.com/sourcegraph/srclib/repo"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

func init() {
	grapher2.Register(&DistPackage{}, grapher2.DockerGrapher{defaultPythonEnv})
}

var notInUnitError = errors.New("not in unit")

var builtinPrefixes = map[string]string{"sys": "sys", "os": "os", "path": "os/path"}

var grapherDockerfileTemplate = template.Must(template.New("").Parse(`FROM dockerfile/java
RUN apt-get update -qq && apt-get install -qq curl git {{.PythonVersion}}
RUN ln -s $(which {{.PythonVersion}}) /usr/bin/python
RUN curl https://raw.githubusercontent.com/pypa/pip/1.5.5/contrib/get-pip.py | python
RUN pip install virtualenv

# Python development headers and other libs that some libraries require to install on Ubuntu
RUN apt-get update -qq && apt-get install -qq python-dev libxslt1-dev libxml2-dev zlib1g-dev

# install python3 version
RUN add-apt-repository ppa:fkrull/deadsnakes > /dev/null  # (TODO: sketchy 3rd party ppa)
RUN apt-get update -qq && apt-get install -qq {{.Python3Version}}
RUN rm /usr/bin/python3
RUN ln -s $(which {{.Python3Version}}) /usr/bin/python3

# Set up virtualenv (will contain dependencies)
RUN virtualenv /venv

# PySonar
RUN apt-get update -qq && apt-get install -qq maven
RUN git clone https://github.com/sourcegraph/pysonar2.git /pysonar2 && cd /pysonar2 && git checkout {{.PySonar2Version}}
WORKDIR /pysonar2
RUN mvn -q clean package
WORKDIR /

# PyDep
RUN pip install git+https://github.com/sourcegraph/pydep.git@{{.PydepVersion}}

# C Module Grapher
RUN apt-get -qq install python3-pip
RUN pip3 install git+https://github.com/sourcegraph/pybuiltingrapher.git@{{.PyBuiltinGrapherVersion}}
`))

var grapherDockerCmdTemplate = template.Must(template.New("").Parse(`
{{if not .IsStdLib}}
echo "attempting to install deps from setup.py" 1>&2;
/venv/bin/pip install {{.SrcDir}} 1>&2;
reqsfiles="{{.SrcDir}}/*requirements.txt";
for r in $reqsfiles; do
  echo "attempting to install deps from $r" 1>&2;
  /venv/bin/pip install -r $r 1>&2;
done
{{end}}

# Compute requirements
{{if .IsStdLib}}
REQDATA='[]'

echo "Graphing C extensions..." 1>&2;
CMODULEGRAPH=$(graphstdlib.py "/src");

{{else}}
REQDATA=$(pydep-run.py dep {{.SrcDir}});
CMODULEGRAPH='null'
{{end}}

# Compute graph
echo 'Running graphing step...' 1>&2;
GRAPHDATA=$(java {{.JavaOpts}} -classpath /pysonar2/target/pysonar-2.0-SNAPSHOT.jar org.yinwang.pysonar.JSONDump {{.SrcDir}} '{{.IncludePaths}}' '');
echo 'Graphing done.' 1>&2;

echo "{ \"graph\": $GRAPHDATA, \"reqs\": $REQDATA, \"extensions\": $CMODULEGRAPH }";
`))

func (p *pythonEnv) grapherDockerfile() []byte {
	var buf bytes.Buffer
	grapherDockerfileTemplate.Execute(&buf, struct {
		*pythonEnv
	}{
		pythonEnv: p,
	})
	return buf.Bytes()
}

func (p *pythonEnv) stdLibDir() string {
	return fmt.Sprintf("/usr/lib/%s", p.PythonVersion)
}

func (p *pythonEnv) sitePackagesDir() string {
	return filepath.Join("/venv", "lib", p.PythonVersion, "site-packages")
}

func (p *pythonEnv) grapherCmd(u unit.SourceUnit, isStdLib bool) []string {
	javaOpts := os.Getenv("PYGRAPH_JAVA_OPTS")
	inclpaths := []string{filepath.Join(srcRoot, u.RootDir()), p.stdLibDir(), p.sitePackagesDir()}

	var buf bytes.Buffer
	grapherDockerCmdTemplate.Execute(&buf, struct {
		JavaOpts     string
		SrcDir       string
		IncludePaths string
		IsStdLib     bool
	}{
		JavaOpts:     javaOpts,
		SrcDir:       filepath.Join(srcRoot, u.RootDir()),
		IncludePaths: strings.Join(inclpaths, ":"),
		IsStdLib:     isStdLib,
	})
	return []string{"/bin/bash", "-c", buf.String()}
}

func (p *pythonEnv) BuildGrapher(dir string, u unit.SourceUnit, c *config.Repository) (*container.Command, error) {
	return &container.Command{
		Container: container.Container{
			RunOptions: []string{"-v", dir + ":" + srcRoot},
			Dockerfile: p.grapherDockerfile(),
			Cmd:        p.grapherCmd(u, c.URI == stdLibRepo || c.URI == extensionsTestRepo),
		},
		Transform: func(orig []byte) ([]byte, error) {
			var o rawGraphData
			err := json.Unmarshal(orig, &o)
			if err != nil {
				outPrefix := string(orig)
				if len(outPrefix) > 100 {
					outPrefix = outPrefix[0:100] + "..."
				}
				return nil, fmt.Errorf("could not unmarshal grapher output as JSON (%s): %s", err, outPrefix)
			}

			o2, err := p.grapherTransform(&o, u)
			if err != nil {
				return nil, err
			}

			b, err := json.Marshal(o2)
			if err != nil {
				return nil, fmt.Errorf("Could not marshal graph JSON: %s", err)
			}
			return b, nil
		},
	}, nil
}

// Transforms pysonar output to our format
func (p *pythonEnv) grapherTransform(o *rawGraphData, u unit.SourceUnit) (*grapher2.Output, error) {
	o.Reqs, _ = pruneReqs(o.Reqs)

	o2 := grapher2.Output{
		Defs: make([]*graph.Def, 0),
		Refs:    make([]*graph.Ref, 0),
		Docs:    make([]*graph.Doc, 0),
	}

	selfrefs := make(map[graph.Ref]struct{})
	for _, pdef := range o.Graph.Defs {
		def, selfref, err := p.convertDef(pdef, u, o.Reqs)
		if err == notInUnitError {
			continue
		}
		if err != nil {
			return nil, fmt.Errorf("could not convert def %+v: %s", pdef, err)
		}

		o2.Defs = append(o2.Defs, def)
		if selfref != nil {
			selfrefs[*selfref] = struct{}{}
			o2.Refs = append(o2.Refs, selfref)
		}
	}
	for _, pref := range o.Graph.Refs {
		ref, err := p.convertRef(pref, u, o.Reqs)
		if err == notInUnitError {
			continue
		}
		if err != nil {
			log.Printf("  (warn) unable to convert reference %+v: %s", pref, err)
			continue
		}

		if _, exists := selfrefs[*ref]; !exists {
			o2.Refs = append(o2.Refs, ref)
		}
	}
	for _, pdoc := range o.Graph.Docs {
		doc, err := p.convertDoc(pdoc, u, o.Reqs)
		if err == notInUnitError {
			continue
		}
		if err != nil {
			return nil, fmt.Errorf("could not convert doc %+v: %s", pdoc, err)
		}
		o2.Docs = append(o2.Docs, doc)
	}

	// Handle the case of C extensions
	if o.Extensions != nil {
		// Extension data includes defs, docs, and self refs. Add those to the struct
		log.Printf("Integrating C extension Defs...")
		o2.Defs = append(o2.Defs, o.Extensions.Defs...)

		log.Printf("Integrating C extension Docs...")
		o2.Docs = append(o2.Docs, o.Extensions.Docs...)

		log.Printf("Integrating C extension Refs...")
		o2.Refs = append(o2.Refs, o.Extensions.Refs...)
	}

	return &o2, nil
}

// Converts a pysonar def into a graph.Def. If err is nil, then def is guaranteed to be not nil. selfref could be
// nil (e.g., in the case that the location of a def's definition name is not well-defined)
func (p *pythonEnv) convertDef(pyDef *pyDef, u unit.SourceUnit, reqs []requirement) (def *graph.Def, selfref *graph.Ref, err error) {
	file, err := p.pysonarFileToFile(u, pyDef.File)
	if err != nil {
		return nil, nil, err
	}
	defKey, err := p.pysonarDefPathToDefKey(pyDef.Path, u, reqs)
	if err != nil {
		return nil, nil, err
	}
	treePath := graph.TreePath(defKey.Path)
	if !treePath.IsValid() {
		return nil, nil, fmt.Errorf("'%s' is not a valid tree-path", treePath)
	}

	def = &graph.Def{
		DefKey: *defKey,
		TreePath:  treePath,
		Name:      pyDef.Name,
		File:      file,
		DefStart:  pyDef.DefStart,
		DefEnd:    pyDef.DefEnd,
		Exported:  pyDef.Exported,
		Callable:  callableDefKinds[pyDef.Kind],
		Kind:      defKinds[pyDef.Kind],
	}

	{
		// Compute data field
		sd := defData{
			Kind: strings.ToLower(pyDef.Kind),
		}

		if pyDef.FuncData != nil {
			sd.FuncSignature = pyDef.FuncData.Signature
		}
		if pyDef.Kind == "MODULE" && strings.HasSuffix(pyDef.File, "__init__.py") {
			sd.Kind = Package
			def.Kind = graph.Package
		}

		b, err := json.Marshal(sd)
		if err != nil {
			return nil, nil, err
		}
		def.Data = b
	}

	{
		// Self ref
		if def.File != "" && pyDef.IdentStart != pyDef.IdentEnd {
			selfref = &graph.Ref{
				DefRepo:     defKey.Repo,
				DefUnitType: defKey.UnitType,
				DefUnit:     defKey.Unit,
				DefPath:     defKey.Path,
				Def:            true,

				Repo:     defKey.Repo,
				UnitType: defKey.UnitType,
				Unit:     defKey.Unit,

				File:  def.File,
				Start: pyDef.IdentStart,
				End:   pyDef.IdentEnd,
			}
		}
	}

	return def, selfref, nil
}

func (p *pythonEnv) convertRef(pyRef *pyRef, u unit.SourceUnit, reqs []requirement) (*graph.Ref, error) {
	refFile, err := p.pysonarFileToFile(u, pyRef.File)
	if err != nil {
		return nil, err
	}
	defKey, err := p.pysonarDefPathToDefKey(pyRef.Def, u, reqs)
	if err != nil {
		return nil, err
	}
	return &graph.Ref{
		DefRepo:     defKey.Repo,
		DefUnitType: defKey.UnitType,
		DefUnit:     defKey.Unit,
		DefPath:     defKey.Path,
		Def:            false,

		Repo:     "", // only care about references located in the current source unit
		UnitType: unit.Type(u),
		Unit:     u.Name(),

		File:  refFile,
		Start: pyRef.Start,
		End:   pyRef.End,
	}, nil
}

func (p *pythonEnv) convertDoc(pyDoc *pyDoc, u unit.SourceUnit, reqs []requirement) (*graph.Doc, error) {
	docFile, err := p.pysonarFileToFile(u, pyDoc.File)
	if err != nil {
		return nil, err
	}
	defKey, err := p.pysonarDefPathToDefKey(pyDoc.Def, u, reqs)
	if err != nil {
		return nil, err
	}
	return &graph.Doc{
		DefKey: *defKey,
		Format:    "text/plain", // TODO: handle rST, HTML, markdown
		Data:      formatDocs(pyDoc.Body),
		File:      docFile,
		Start:     pyDoc.Start,
		End:       pyDoc.End,
	}, nil
}

func (p *pythonEnv) pysonarFileToFile(u unit.SourceUnit, pfile string) (file string, err error) {
	relpath, err := filepath.Rel(filepath.Join(srcRoot, u.RootDir()), pfile)
	if err != nil {
		return "", err
	}
	if strings.HasPrefix(relpath, "..") {
		return "", notInUnitError
	}
	return filepath.Join(u.RootDir(), relpath), nil
}

// Transforms a def path emitted from PySonar into a DefKey. PySonar def paths are absolute in the filesystem
// (although they don't represent files), so we can reconstruct the source of the def (repository and unit) from
// them.
//
// Assumptions: All top-level modules/packages are a direct child of the *source unit* root directory (the dir that
// contains the setup.py). I.e., if the source unit root is flask/ (i.e., there exists a flask/setup.py) that contains a
// package, flask, then flask/flask/__init__.py must exist. Something like flask/src/flask/__init__.py is unacceptable.
// (It's possible to support this in the future, but we must parse the package_dir argument to setup() in setup.py
// (EASY) and somehow make this available for installed dependencies (HARD, because we don't have the setup.py after
// installation).
func (p *pythonEnv) pysonarDefPathToDefKey(pyDefPath string, u unit.SourceUnit, reqs []requirement) (*graph.DefKey, error) {
	var uDir = filepath.Join(srcRoot, u.RootDir())
	if relpath, err := filepath.Rel(uDir, pyDefPath); err == nil && !strings.HasPrefix(relpath, "..") {
		// Case 1: in current source unit (u)
		return &graph.DefKey{
			// no repo URI means same repo
			UnitType: unit.Type(u),
			Unit:     u.Name(),
			Path:     graph.DefPath(relpath),
		}, nil
	} else if relpath, err := filepath.Rel(p.sitePackagesDir(), pyDefPath); err == nil && !strings.HasPrefix(relpath, "..") {
		// Case 2: in dependent source unit(depUnits)
		var foundReq *requirement
		candidates := make([]string, 0)
	FindReq:
		for _, req := range reqs {
			for _, pkg := range req.Packages {
				pkgpath := filepath.Join(p.sitePackagesDir(), pkg)
				if r, err := filepath.Rel(pkgpath, pyDefPath); err == nil && !strings.HasPrefix(r, "..") {
					foundReq = &req
					break FindReq
				}
				if len(candidates) < 7 {
					candidates = append(candidates, pkg)
				} else if len(candidates) == 7 {
					candidates = append(candidates, "and more...")
				}
			}
			for _, mod := range req.Modules {
				modpath := filepath.Join(p.sitePackagesDir(), mod) // TODO(bliu): add a test case for top-level module libs
				if r, err := filepath.Rel(modpath, pyDefPath); err == nil && !strings.HasPrefix(r, "..") {
					foundReq = &req
					break FindReq
				}
				candidates = append(candidates, mod)
			}
		}
		if foundReq == nil {
			return nil, fmt.Errorf("Could not find requirement matching path %s, stdlib-dir: %s, site-packages-dir: %s with candidates %v",
				pyDefPath, p.stdLibDir(), p.sitePackagesDir(), candidates)
		}

		var reqUnit = foundReq.DistPackage()
		return &graph.DefKey{
			Repo:     repo.MakeURI(foundReq.RepoURL),
			UnitType: unit.Type(reqUnit),
			Unit:     reqUnit.Name(),
			Path:     graph.DefPath(relpath),
		}, nil
	} else if relpath, err := filepath.Rel(p.stdLibDir(), pyDefPath); err == nil && !strings.HasPrefix(relpath, "..") {
		// Case 3: in std lib
		return &graph.DefKey{
			Repo:     stdLibRepo,
			UnitType: unit.Type(stdLibUnit),
			Unit:     stdLibUnit.Name(),
			Path:     graph.DefPath(relpath),
		}, nil
	} else {
		// Case 4: built-in def or error
		for prefix, newPrefix := range builtinPrefixes {
			if strings.HasPrefix(pyDefPath, prefix) {
				return &graph.DefKey{
					Repo:     stdLibRepo,
					UnitType: unit.Type(stdLibUnit),
					Unit:     stdLibUnit.Name(),
					Path:     graph.DefPath(strings.Replace(pyDefPath, prefix, newPrefix, 1)),
				}, nil
			}
		}
		return nil, fmt.Errorf("Could not find requirement matching PySonar path %s", pyDefPath)
	}
}

type graphData_ struct {
	Defs []*pyDef
	Refs []*pyRef
	Docs []*pyDoc
}

type rawGraphData struct {
	Graph      graphData_
	Reqs       []requirement
	Extensions *grapher2.Output
}

type pyDef struct {
	Path       string
	Name       string
	File       string
	IdentStart int
	IdentEnd   int
	DefStart   int
	DefEnd     int
	Exported   bool
	Kind       string
	FuncData   *struct {
		Signature string
	} `json:",omitempty"`
}

type pyRef struct {
	Def     string
	File    string
	Start   int
	End     int
	Builtin bool
}

type pyDoc struct {
	Def   string
	File  string
	Body  string
	Start int
	End   int
}

// defData is stored in graph.Def's Data field as JSON.
type defData struct {
	Kind          string
	FuncSignature string
}
