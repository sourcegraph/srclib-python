// +build off

// TODO(bliu): revisit this

package python

import "sourcegraph/sourcegraph.com/srclib/config"

func init() {
	config.Register("python", &Config{})
}

type Config struct {
	SrcDir      string   // directory that contains source code
	ExamplesDir string   // directory that contains example code
	DocDir      string   // directory that contains sphinx docs
	TopLevel    []string // top-level modules and packages
}
