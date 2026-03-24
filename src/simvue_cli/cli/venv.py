"""Simvue Virtual Environment Commands."""

import click
import sys

import simvue_cli.actions


@click.command("venv")
@click.pass_context
@click.option(
    "--language",
    required=True,
    help="Specify target language",
    type=click.Choice(["python", "rust", "julia", "nodejs"]),
)
@click.option(
    "--run", required=False, help="ID of run to clone environment from", default=""
)
@click.option(
    "--allow-existing",
    is_flag=True,
    help="Install dependencies in an existing environment",
)
@click.argument("venv_directory", type=click.Path(exists=False))
def venv_setup(ctx, **kwargs) -> None:
    """Initialise virtual environments from run metadata.

    If a run ID is not provided via --run it is read from stdin.
    """
    if not kwargs.get("run"):
        kwargs["run"] = input()

    try:
        simvue_cli.actions.create_environment(**kwargs)
    except (FileExistsError, RuntimeError) as e:
        error_msg = e.args[0]
        if ctx.obj["plain"]:
            click.echo(error_msg)
        else:
            click.secho(error_msg, fg="red", bold=True)
        sys.exit(1)
