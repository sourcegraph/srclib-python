// +build off
package python

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

var defKinds = map[string]string{
	"ATTRIBUTE":   "field",
	"CLASS":       "type",
	"CONSTRUCTOR": "func",
	"FUNCTION":    "func",
	"METHOD":      "func",
	"MODULE":      "module",
	"PACKAGE":     "package",
	"PARAMETER":   "var",
	"SCOPE":       "var",
	"VARIABLE":    "var",
}
