package container

import (
	"context"
	"fmt"
	"io"

	"github.com/docker/cli/cli"
	"github.com/docker/cli/cli/command"
	"github.com/docker/cli/cli/config/configfile"
	"github.com/docker/cli/opts"
	"github.com/docker/docker/api/types"
	apiclient "github.com/docker/docker/client"
	"github.com/pkg/errors"
	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
)

type execOptions struct {
	DetachKeys  string
	Interactive bool
	Tty         bool
	Detach      bool
	User        string
	Privileged  bool
	Env         opts.ListOpts
	Workdir     string
	Container   string
	Command     []string
}

func NewExecOptions() execOptions {
	return execOptions{Env: opts.NewListOpts(opts.ValidateEnv)}
}

// NewExecCommand creates a new cobra.Command for `docker exec`
func NewExecCommand(dockerCli command.Cli) *cobra.Command {
	options := NewExecOptions()

	cmd := &cobra.Command{
		Use:   "exec [OPTIONS] CONTAINER COMMAND [ARG...]",
		Short: "Run a command in a running container",
		Args:  cli.RequiresMinArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			options.Container = args[0]
			fmt.Println("container name " + options.Container)
			options.Command = args[1:]
			fmt.Println("command length: ")
			fmt.Println(len(options.Command))
			for _, i := range options.Command {
				fmt.Println(i)
			}
			return RunExec(dockerCli, options)
		},
	}

	flags := cmd.Flags()
	flags.SetInterspersed(false)

	flags.StringVarP(&options.DetachKeys, "detach-keys", "", "", "Override the key sequence for detaching a container")
	flags.BoolVarP(&options.Interactive, "interactive", "i", false, "Keep STDIN open even if not attached")
	flags.BoolVarP(&options.Tty, "tty", "t", false, "Allocate a pseudo-TTY")
	flags.BoolVarP(&options.Detach, "detach", "d", false, "Detached mode: run command in the background")
	flags.StringVarP(&options.User, "user", "u", "", "Username or UID (format: <name|uid>[:<group|gid>])")
	flags.BoolVarP(&options.Privileged, "privileged", "", false, "Give extended privileges to the command")
	flags.VarP(&options.Env, "env", "e", "Set environment variables")
	flags.SetAnnotation("env", "version", []string{"1.25"})
	flags.StringVarP(&options.Workdir, "workdir", "w", "", "Working directory inside the container")
	flags.SetAnnotation("workdir", "version", []string{"1.35"})

	return cmd
}

func RunExec(dockerCli command.Cli, options execOptions) error {
	fmt.Println("runExec")
	execConfig := parseExec(options, dockerCli.ConfigFile())
	ctx := context.Background()
	client := dockerCli.Client()

	// We need to check the tty _before_ we do the ContainerExecCreate, because
	// otherwise if we error out we will leak execIDs on the server (and
	// there's no easy way to clean those up). But also in order to make "not
	// exist" errors take precedence we do a dummy inspect first.
	if _, err := client.ContainerInspect(ctx, options.Container); err != nil {
		return err
	}
	if !execConfig.Detach {
		if err := dockerCli.In().CheckTty(execConfig.AttachStdin, execConfig.Tty); err != nil {
			return err
		}
	}

	response, err := client.ContainerExecCreate(ctx, options.Container, *execConfig)
	if err != nil {
		return err
	}

	execID := response.ID
	if execID == "" {
		return errors.New("exec ID empty")
	}

	if execConfig.Detach {
		execStartCheck := types.ExecStartCheck{
			Detach: execConfig.Detach,
			Tty:    execConfig.Tty,
		}
		return client.ContainerExecStart(ctx, execID, execStartCheck)
	}
	return interactiveExec(ctx, dockerCli, execConfig, execID)
}

func interactiveExec(ctx context.Context, dockerCli command.Cli, execConfig *types.ExecConfig, execID string) error {
	// Interactive exec requested.
	fmt.Println("interactive exec")
	var (
		out, stderr io.Writer
		in          io.ReadCloser
	)

	if execConfig.AttachStdin {
		in = dockerCli.In()
	}
	if execConfig.AttachStdout {
		out = dockerCli.Out()
	}
	if execConfig.AttachStderr {
		if execConfig.Tty {
			stderr = dockerCli.Out()
		} else {
			stderr = dockerCli.Err()
		}
	}

	client := dockerCli.Client()
	execStartCheck := types.ExecStartCheck{
		Tty: execConfig.Tty,
	}
	resp, err := client.ContainerExecAttach(ctx, execID, execStartCheck)
	if err != nil {
		return err
	}
	defer resp.Close()

	errCh := make(chan error, 1)

	go func() {
		defer close(errCh)
		errCh <- func() error {
			streamer := hijackedIOStreamer{
				streams:      dockerCli,
				inputStream:  in,
				outputStream: out,
				errorStream:  stderr,
				resp:         resp,
				tty:          execConfig.Tty,
				detachKeys:   execConfig.DetachKeys,
			}

			return streamer.stream(ctx)
		}()
	}()

	if execConfig.Tty && dockerCli.In().IsTerminal() {
		if err := MonitorTtySize(ctx, dockerCli, execID, true); err != nil {
			fmt.Fprintln(dockerCli.Err(), "Error monitoring TTY size:", err)
		}
	}

	if err := <-errCh; err != nil {
		logrus.Debugf("Error hijack: %s", err)
		return err
	}

	return getExecExitStatus(ctx, client, execID)
}

func getExecExitStatus(ctx context.Context, client apiclient.ContainerAPIClient, execID string) error {
	fmt.Println("exiting")
	resp, err := client.ContainerExecInspect(ctx, execID)
	if err != nil {
		// If we can't connect, then the daemon probably died.
		if !apiclient.IsErrConnectionFailed(err) {
			return err
		}
		return cli.StatusError{StatusCode: -1}
	}
	status := resp.ExitCode
	if status != 0 {
		return cli.StatusError{StatusCode: status}
	}
	return nil
}

// parseExec parses the specified args for the specified command and generates
// an ExecConfig from it.
func parseExec(opts execOptions, configFile *configfile.ConfigFile) *types.ExecConfig {
	fmt.Println("parseExec")
	execConfig := &types.ExecConfig{
		User:       opts.User,
		Privileged: opts.Privileged,
		Tty:        opts.Tty,
		Cmd:        opts.Command,
		Detach:     opts.Detach,
		Env:        opts.Env.GetAll(),
		WorkingDir: opts.Workdir,
	}

	// If -d is not set, attach to everything by default
	if !opts.Detach {
		execConfig.AttachStdout = true
		execConfig.AttachStderr = true
		if opts.Interactive {
			execConfig.AttachStdin = true
		}
	}

	if opts.DetachKeys != "" {
		execConfig.DetachKeys = opts.DetachKeys
	} else {
		execConfig.DetachKeys = configFile.DetachKeys
	}
	return execConfig
}