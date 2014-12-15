package python

import (
	"log"

	"sourcegraph.com/sourcegraph/srclib"
	"sourcegraph.com/sourcegraph/srclib/graph"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

const (
	DistPackageSourceUnitType = "PipPackage"
)

type pythonEnv struct {
	PythonVersion           string
	Python3Version          string
	PydepVersion            string
	PySonar2Version         string
	PyBuiltinGrapherVersion string
}

var defaultPythonEnv = &pythonEnv{
	PythonVersion:           "python2.7",
	Python3Version:          "python3.3",
	PydepVersion:            "debfd0e681c3b60e33eec237a4473aed1f767004",
	PySonar2Version:         "1b152a16d1292b66280e60047a8dbdbfc86a103b",
	PyBuiltinGrapherVersion: "4a2e5de8cd6788198339b4a384c659ce2deee3b6",
}

// func init() {
// 	toolchain.Register("python", defaultPythonEnv)
// }

/*
const DistPackageDisplayName = "PipPackage"

type DistPackage struct {
	// Name of the DistPackage as defined in setup.py. E.g., Django, Flask, etc.
	ProjectName string

	// Description of the DistPackage (extracted from its setup.py). This may be empty if derived from a requirement.
	ProjectDescription string

	// The root directory relative to the repository root that contains the setup.py. This may be empty if this
	// DistPackage is derived from a requirement (there is no way to recover a Python distUtils package's location in
	// its source repository without accessing the source repository itself).
	RootDirectory string

	// The files in the package. This may be empty (it is only necessary for computing blame).
	Files []string
}

func (p *DistPackage) Name() string {
	return p.ProjectName
}

func (p *DistPackage) RootDir() string {
	return p.RootDirectory
}

func (p *DistPackage) Paths() []string {
	paths := make([]string, len(p.Files))
	for i, f := range p.Files {
		paths[i] = filepath.Join(p.RootDirectory, f)
	}
	return paths
}

// NameInRepository implements unit.Info.
func (p *DistPackage) NameInRepository(defining string) string { return p.Name() }

// GlobalName implements unit.Info.
func (p *DistPackage) GlobalName() string { return p.Name() }

// Description implements unit.Info.
func (p *DistPackage) Description() string { return p.ProjectDescription }

// Type implements unit.Info.
func (p *DistPackage) Type() string { return "Python package" }
*/

// pydep data structures

// Format outputted by scanner
type pkgInfo struct {
	RootDir     string   `json:"rootdir,omitempty"`
	ProjectName string   `json:"project_name,omitempty"`
	Version     string   `json:"version,omitempty"`
	RepoURL     string   `json:"repo_url,omitempty"`
	Packages    []string `json:"packages,omitempty"`
	Modules     []string `json:"modules,omitempty"`
	Scripts     []string `json:"scripts,omitempty"`
	Author      string   `json:"author,omitempty"`
	Description string   `json:"description,omitempty"`
}

func (p *pkgInfo) SourceUnit() *unit.SourceUnit {
	repoURI, err := graph.TryMakeURI(p.RepoURL)
	if err != nil {
		log.Printf("Could not make repo URI from %s: %s", p.RepoURL, err)
		repoURI = ""
	}
	return &unit.SourceUnit{
		Name:         p.ProjectName,
		Type:         DistPackageSourceUnitType,
		Repo:         repoURI,
		Dir:          p.RootDir,
		Dependencies: nil, // nil, because scanner does not resolve dependencies
		Ops:          map[string]*srclib.ToolRef{"depresolve": nil, "graph": nil},
	}
}

/*
func (p pkgInfo) DistPackage() *DistPackage {
	return &DistPackage{
		ProjectName:        p.ProjectName,
		ProjectDescription: p.Description,
		RootDirectory:      p.RootDir,
	}
}

func (p pkgInfo) DistPackageWithFiles(files []string) *DistPackage {
	return &DistPackage{
		ProjectName:        p.ProjectName,
		ProjectDescription: p.Description,
		RootDirectory:      p.RootDir,
		Files:              files,
	}
}
*/

type requirement struct {
	ProjectName string      `json:"project_name"`
	UnsafeName  string      `json:"unsafe_name"`
	Key         string      `json:"key"`
	Specs       [][2]string `json:"specs"`
	Extras      []string    `json:"extras"`
	RepoURL     string      `json:"repo_url"`
	Packages    []string    `json:"packages"`
	Modules     []string    `json:"modules"`
	Resolved    bool        `json:"resolved"`
	Type        string      `json:"type"`
}

func (r *requirement) SourceUnit() *unit.SourceUnit {
	return &unit.SourceUnit{
		Name: r.ProjectName,
		Type: DistPackageSourceUnitType,
		Repo: graph.MakeURI(r.RepoURL),
	}
}

/*
func (l *pythonEnv) pydepDockerfile() ([]byte, error) {
	var buf bytes.Buffer
	template.Must(template.New("").Parse(pydepDockerfileTemplate)).Execute(&buf, l)
	return buf.Bytes(), nil
}

const pydepDockerfileTemplate = `FROM ubuntu:14.04
RUN apt-get update -qq && apt-get install -qq curl git {{.PythonVersion}}
RUN ln -s $(which {{.PythonVersion}}) /usr/bin/python
RUN curl https://raw.githubusercontent.com/pypa/pip/1.5.5/contrib/get-pip.py | python

# Python development headers and other libs that some libraries require to install on Ubuntu
RUN apt-get update -qq && apt-get install -qq python-dev libxslt1-dev libxml2-dev zlib1g-dev

RUN pip install git+git://github.com/sourcegraph/pydep.git@{{.PydepVersion}}
`
*/
