package python

import (
	"log"
	"os"
	"os/exec"
	"strings"
)

func runCmdLogError(cmd *exec.Cmd) {
	err := runCmdStderr(cmd)
	if err != nil {
		log.Printf("Error running `%s`: %s", strings.Join(cmd.Args, " "), err)
	}
}

func runCmdStderr(cmd *exec.Cmd) error {
	cmd.Stderr = os.Stderr
	cmd.Stdout = os.Stderr
	return cmd.Run()
}
