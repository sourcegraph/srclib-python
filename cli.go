package main

import (
	"encoding/json"

	"log"
	"os"
	"path/filepath"

	"github.com/jessevdk/go-flags"
	"sourcegraph.com/sourcegraph/srclib-python/python"
	"sourcegraph.com/sourcegraph/srclib/dep"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

var (
	parser = flags.NewNamedParser("srclib-python", flags.Default)
	cwd    string
)

func init() {
	parser.LongDescription = "srclib-python performs Python package, dependency, and source analysis."

	var err error
	cwd, err = os.Getwd()
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	log.SetFlags(0)
	if _, err := parser.Parse(); err != nil {
		os.Exit(1)
	}
}

func init() {
	_, err := parser.AddCommand("scan",
		"scan for Python packages",
		"Scan the directory tree rooted at the current directory for Python packages.",
		&scanCmd,
	)
	if err != nil {
		log.Fatal(err)
	}
}

type ScanCmd struct {
	Repo   string `long:"repo" description:"repository URI" value-name:"URI"`
	Subdir string `long:"subdir" description:"subdirectory in repository" value-name:"DIR"`
}

var scanCmd ScanCmd

func (c *ScanCmd) Execute(args []string) error {
	units, err := python.Scan(".", c.Repo, c.Subdir)
	if err != nil {
		return err
	}

	if err := json.NewEncoder(os.Stdout).Encode(units); err != nil {
		return err
	}
	return nil
}

func init() {
	_, err := parser.AddCommand("depresolve",
		"resolve a Python distutils package's imports",
		"Resolve a Python distutils package's imports to their repository clone URL.",
		&depResolveCmd,
	)
	if err != nil {
		log.Fatal(err)
	}
}

type DepResolveCmd struct{}

var depResolveCmd DepResolveCmd

func (c *DepResolveCmd) Execute(args []string) error {
	var unit *unit.SourceUnit
	if err := json.NewDecoder(os.Stdin).Decode(&unit); err != nil {
		return err
	}
	if err := os.Stdin.Close(); err != nil {
		return err
	}

	res := make([]*dep.Resolution, len(unit.Dependencies))
	for i, rawDep := range unit.Dependencies {
		res[i] = &dep.Resolution{Raw: rawDep}

		rt, err := python.ResolveDep(rawDep)
		if err != nil {
			res[i].Error = err.Error()
			continue
		}
		res[i].Target = rt
	}

	if err := json.NewEncoder(os.Stdout).Encode(res); err != nil {
		return err
	}
	return nil
}

func init() {
	_, err := parser.AddCommand("graph",
		"graph a Python distutils package",
		"Graph a Python distutils package, producing all defs, refs, and docs.",
		&graphCmd,
	)
	if err != nil {
		log.Fatal(err)
	}
}

type GraphCmd struct{}

var graphCmd GraphCmd

func (c *GraphCmd) Execute(args []string) error {
	var unit *unit.SourceUnit
	if err := json.NewDecoder(os.Stdin).Decode(&unit); err != nil {
		return err
	}
	if err := os.Stdin.Close(); err != nil {
		return err
	}

	if os.Getenv("IN_DOCKER_CONTAINER") != "" {
		// TODO: install pip dependencies
	}

	out, err := python.Graph(unit)
	if err != nil {
		return err
	}

	// Make paths relative to repo.
	for _, gs := range out.Symbols {
		if gs.File == "" {
			log.Printf("no file %+v", gs)
		}
		gs.File = relPath(cwd, gs.File)
	}
	for _, gr := range out.Refs {
		gr.File = relPath(cwd, gr.File)
	}
	for _, gd := range out.Docs {
		if gd.File != "" {
			gd.File = relPath(cwd, gd.File)
		}
	}

	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		return err
	}
	return nil
}

func relPath(cwd, path string) string {
	rp, err := filepath.Rel(cwd, path)
	if err != nil {
		log.Fatalf("Failed to make path %q relative to %q: %s", path, cwd, err)
	}
	return rp
}
