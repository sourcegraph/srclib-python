package python

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/kr/fs"

	"sourcegraph.com/sourcegraph/srclib/unit"
)

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
	}

	return units, nil
}

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
