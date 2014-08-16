package python

import (
	"log"
	"os"
	"os/exec"
	"strings"
)

func runCmdLogError(cmd *exec.Cmd) {
	cmd.Stderr = os.Stderr
	cmd.Stdout = os.Stderr
	err := cmd.Run()
	if err != nil {
		log.Printf("Error running `%s`: %s", strings.Join(cmd.Args, " "), err)
	}
}
