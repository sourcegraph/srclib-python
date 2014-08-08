// +build off
package python

import "sourcegraph.com/sourcegraph/srclib/graph"

const (
	Package = "package"
	Module  = "module"

	// Other def kinds are defined in the Python code and passed through
	// verbatim (except for being lowercased): ATTRIBUTE, CLASS, CONSTRUCTOR,
	// etc.
)

var callableDefKinds = map[string]bool{
	"CONSTRUCTOR": true,
	"FUNCTION":    true,
	"METHOD":      true,
}

var defKinds = map[string]graph.DefKind{
	"ATTRIBUTE":   graph.Field,
	"CLASS":       graph.Type,
	"CONSTRUCTOR": graph.Func,
	"FUNCTION":    graph.Func,
	"METHOD":      graph.Func,
	"MODULE":      graph.Module,
	"PACKAGE":     graph.Package,
	"PARAMETER":   graph.Var,
	"SCOPE":       graph.Var,
	"VARIABLE":    graph.Var,
}
