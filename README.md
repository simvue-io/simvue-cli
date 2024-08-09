# Simvue CLI

![cli_image](https://raw.githubusercontent.com/simvue-io/simvue-cli/main/CLI_image.png)

Simvue CLI is a command line interface for interacting with a Simvue server instance. The tool is designed to aid in performing more basic operations compared to the Simvue Python API which should be used instead for more complicated parsing of data and execution of simulations.

## Modifying Simvue configuration

You can use Simvue CLI to simplify modification of the Simvue configuration files, to set the server URL:

```sh
simvue config server.url <server-url>
```

and to update the token for this server:

```sh
simvue config server.token <server-token>
```

By default these settings are applied a configuration file located within the current working directory. To instead set these settings globally use the `--global` flag.

## Retrieving and creating runs

Run interaction is performed using the `run` subcommand.

### Listing runs

To list all runs on the server use:

```sh
simvue run list
```

By default this will be limited to 20 runs, this behaviour can be changed by using the `--count` option.

#### Adding output columns

Additional information can be displayed by using the relevant flag:

```sh
simvue run list --tags --name
```

The full list of available flags is given by running with `--help`.

#### Formatting the output

By default the output is not formatted, Simvue CLI makes use of the `tabulate` module to improve displaying of results, simply use the `--format` option to select from all possibilities, a full list is given under `--help`:

```sh
simvue run list --format rounded_outline
```

#### Display run info

You can retrieve all information from a run as a JSON string, use of `jq` to query this output is recommended:

```sh
simvue run json <run-id> | jq
```

The `json` command is also designed to support piping, we can retrieve the latest run and query it:

```sh
simvue run list --count 1 | simvue json | jq 
```

### Creating runs

To create a run execute:

```sh
simvue run create
```

this will return the unique run identifier.

### Logging metrics and events

Events and metrics can be logged to a created run, for metrics the input is expected to be a JSON parsible string:

```sh
simue run log.metrics <run-id> "{'x': 1, 'y': 2}"
```

For events the input is just the event message as a string:

```sh
simvue run log.event <run-id> "Hello World!"
```

### Terminating runs

Make sure to close your runs! The following commands close or abort the run:

```sh
simvue run close <run-id>
```

```sh
simvue run abort <run-id>
```

## Monitoring stdout

In the rare case where a program writes out only delimited data you can directly log this output as metrics. For example taking the simple bash script:

```bash
# Firstly echo headers
echo "x\ty"

# Now the data
for i in {1..10}; do
  echo "$i\t$((i * 2))"
  sleep 1
done
```

We could send this data direct to Simvue:

```sh
bash my_script.sh | simvue monitor
```

## Creating user alerts

User (or manually triggered) alerts can be created on the command line:

```sh
simvue alert create "my_alert"
```

The additional options `--email` and `--abort` define if triggering of the alert sends an email notification and whether when the alert is triggered an abort is called respectively.

## Clearing local files

The command `purge` will remove all local Simvue files:

```sh
simvue purge
```

## Version information

Aside from the standard `--version` flag to the `simvue` command you can view also the API and server versions via:

```sh
simvue about
```

## Plain output

In cases where terminal colors or formatting are unavailable you can instead run with the `--plain` option applied to the main `simvue` command, e.g.:

```sh
simvue --plain run list
```
