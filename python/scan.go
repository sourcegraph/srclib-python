package python

import (
	"encoding/json"
	"log"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/kr/fs"

	"sourcegraph.com/sourcegraph/srclib/toolchain"
	"sourcegraph.com/sourcegraph/srclib/unit"
)

// Scan a directory, listing all source units
func Scan(srcdir string, repoURI string, repoSubdir string) ([]*unit.SourceUnit, error) {
	if units, isSpecial := specialUnits[repoURI]; isSpecial {
		return units, nil
	}

	cmd := exec.Command("pydep-run.py", "list", srcdir)

	cmd.Stderr = os.Stderr
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err := cmd.Start(); err != nil {
		return nil, err
	}

	var pkgs []*pkgInfo
	if err := json.NewDecoder(stdout).Decode(&pkgs); err != nil {
		return nil, err
	}

	if err := cmd.Wait(); err != nil {
		return nil, err
	}

	units := make([]*unit.SourceUnit, len(pkgs))
	for i, pkg := range pkgs {
		units[i] = pkg.SourceUnit()
		units[i].Files = pythonSourceFiles(pkg.RootDir)

		reqs, err := requirements(pkg.RootDir)
		if err != nil {
			return nil, err
		}
		reqs_ := make([]interface{}, len(reqs))
		for i, req := range reqs {
			reqs_[i] = req
		}
		units[i].Dependencies = reqs_
	}

	//TODO(rameshvarun): Scan for packages based off __init__.py files

	scriptUnits := findScripts(srcdir, units)
	units = append(units, scriptUnits...)

	return units, nil
}

// Checks to see if a script is accounted for in the files of the given units
func scriptInUnits(script_file string, units []*unit.SourceUnit) bool {
	for _, unit := range units {
		for _, file := range unit.Files {
			if script_file == file {
				return true
			}
		}
	}
	return false
}

// Scan for single file scripts that are not part of any PIP packages
func findScripts(dir string, units []*unit.SourceUnit) []*unit.SourceUnit {
	var scriptUnits []*unit.SourceUnit

	walker := fs.Walk(dir)
	for walker.Step() {
		if err := walker.Err(); err == nil && !walker.Stat().IsDir() && filepath.Ext(walker.Path()) == ".py" {
			file, _ := filepath.Rel(dir, walker.Path())

			if(!scriptInUnits(file, units)) {
				scriptUnit := unit.SourceUnit {
					Name: file,
					Type: "PythonScript",
					Files: []string{file},
					Dir: filepath.Dir(file),
					Dependencies: nil,
					Ops: map[string]*toolchain.ToolRef{"depresolve": nil, "graph": nil},
				}

				scriptUnits = append(scriptUnits, &scriptUnit)
			}
		}
	}

	return scriptUnits;
}

func requirements(unitDir string) ([]*requirement, error) {
	depCmd := exec.Command("pydep-run.py", "dep", unitDir)
	depCmd.Stderr = os.Stderr
	b, err := depCmd.Output()
	if err != nil {
		return nil, err
	}

	var reqs []*requirement
	err = json.Unmarshal(b, &reqs)
	if err != nil {
		return nil, err
	}
	reqs, ignoredReqs := pruneReqs(reqs)
	if len(ignoredReqs) > 0 {
		ignoredKeys := make([]string, len(ignoredReqs))
		for r, req := range ignoredReqs {
			ignoredKeys[r] = req.Key
		}
		log.Printf("(warn) ignoring dependencies %v because repo URL absent", ignoredKeys)
	}

	return reqs, nil
}

// Get all python source files under dir
func pythonSourceFiles(dir string) (files []string) {
	walker := fs.Walk(dir)
	for walker.Step() {
		if err := walker.Err(); err == nil && !walker.Stat().IsDir() && filepath.Ext(walker.Path()) == ".py" {
			file, _ := filepath.Rel(dir, walker.Path())
			files = append(files, file)
		}
	}
	return
}

// Remove unresolvable requirements (i.e., requirements with no clone URL)
func pruneReqs(reqs []*requirement) (kept, ignored []*requirement) {
	for _, req := range reqs {
		if req.RepoURL != "" { // cannot resolve dependencies with no clone URL
			kept = append(kept, req)
		} else {
			ignored = append(ignored, req)
		}
	}
	return
}
