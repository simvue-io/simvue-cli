"""
Simvue CLI
==========

Command line tool for interfacing with a Simvue server, this interface allows
the user to submit metrics and retrieve information from the command line.
"""

import pathlib
import sys
import shutil
import click
import click_log
import click_option_group
import logging
from simvue.run import json
import tabulate

import simvue_cli.config
import simvue_cli.run

from simvue_cli.cli.display import create_runs_display
from simvue_cli.types import SimvueName, SimvueFolder, JSONType

from click_params import PUBLIC_URL

logger = logging.getLogger()
click_log.basic_config(logger)


@click.group("simvue")
@click_log.simple_verbosity_option(logger)
@click.option(
    "--plain", help="Run without color/formatting", default=False, is_flag=True
)
@click.pass_context
def simvue(ctx, plain: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["plain"] = plain


@simvue.group("config")
@click.option(
    "--local/--global",
    default=True,
    help="Update local or global configurations",
    show_default=True,
)
@click.pass_context
def config(ctx, local: bool) -> None:
    """Configure Simvue"""
    ctx.obj["local"] = local


@config.command("server.url")
@click.argument("url", type=PUBLIC_URL)
@click.pass_context
def config_set_url(ctx, url: str) -> None:
    """Update Simvue configuration URL"""
    out_file: pathlib.Path = simvue_cli.config.set_configuration_option(
        section="server", key="url", value=url, local=ctx.obj["local"]
    )
    click.secho(f"Wrote URL value to '{out_file}'")


@config.command("server.token")
@click.argument("token", type=str)
@click.pass_context
def config_set_token(ctx, token: str) -> None:
    """Update Simvue configuration Token"""
    out_file: pathlib.Path = simvue_cli.config.set_configuration_option(
        section="server", key="token", value=token, local=ctx.obj["local"]
    )
    click.secho(f"Wrote token value to '{out_file}'")


@simvue.group("run")
@click.pass_context
def simvue_run(ctx) -> None:
    """Create or retrieve Simvue runs"""
    pass


@simvue_run.command("create")
@click.pass_context
@click.option(
    "--create-only", help="Create run but do not start it", is_flag=True, default=False
)
@click_option_group.optgroup.group(
    "Run attributes",
    help="Assign properties such as metadata and labelling to this run",
)
@click_option_group.optgroup.option(
    "--name", type=SimvueName, help="Name to assign to this run", default=None
)
@click_option_group.optgroup.option(
    "--description", type=str, help="Short run description", default=None
)
@click_option_group.optgroup.option(
    "--tag", type=str, help="Tag this run with a label", default=None, multiple=True
)
@click_option_group.optgroup.option(
    "--folder",
    type=SimvueFolder,
    help="Specify folder path for this run",
    default="/",
    show_default=True,
)
def create_run(
    ctx, create_only: bool, tag: tuple[str, ...] | None, **run_params
) -> None:
    """Initialise a new Simvue run"""
    run_params |= {"running": not create_only, "tags": list(tag) if tag else None}
    run_id: str = simvue_cli.run.create_simvue_run(**run_params)

    click.echo(click.style(run_id) if not ctx.obj["plain"] else run_id)


@simvue_run.command("close")
@click.pass_context
@click.argument("run_id", type=str)
def close_run(ctx, run_id: str) -> None:
    """Mark an active run as completed"""
    if not (simvue_cli.run.get_run(run_id)):
        error_msg = f"Run '{run_id}' not found"
        if ctx.obj["plain"]:
            print(error_msg)
        else:
            click.secho(error_msg, fg="red", bold=True)
        sys.exit(1)
    try:
        simvue_cli.run.set_run_status(run_id, "completed")
    except ValueError as e:
        click.echo(
            click.style(e.args[0], fg="red", bold=True)
            if not ctx.obj["plain"]
            else e.args[0]
        )
        sys.exit(1)


@simvue_run.command("abort")
@click.pass_context
@click.argument("run_id", type=str)
@click.option(
    "--reason",
    type=str,
    help="Reason for abort",
    default="Manual termination via CLI",
    show_default=True,
)
def abort_run(ctx, run_id: str, reason: str) -> None:
    """Abort an active run"""
    if not (simvue_cli.run.get_run(run_id)):
        error_msg = f"Run '{run_id}' not found"
        if ctx.obj["plain"]:
            print(error_msg)
        else:
            click.secho(error_msg, fg="red", bold=True)
        sys.exit(1)
    simvue_cli.run.set_run_status(run_id, "aborted", reason=reason)


@simvue_run.command("log.metrics")
@click.argument("run_id", type=str)
@click.argument("metrics", type=JSONType)
def log_metrics(run_id: str, metrics: dict) -> None:
    """Log metrics to Simvue server"""
    simvue_cli.run.log_metrics(run_id, metrics)


@simvue_run.command("log.event")
@click.argument("run_id", type=str)
@click.argument("event_message", type=str)
def log_event(run_id: str, event_message: str) -> None:
    """Log event to Simvue server"""
    simvue_cli.run.log_event(run_id, event_message)


@simvue_run.command("list")
@click.pass_context
@click.option(
    "--format",
    type=click.Choice(list(tabulate._table_formats.keys())),
    help="Display as table with output format",
    default=None,
)
@click.option(
    "--enumerate",
    "enumerate_",
    is_flag=True,
    help="Show counter next to runs",
    default=False,
    show_default=True,
)
@click.option(
    "--count",
    type=int,
    help="Maximum number of runs to retrieve",
    default=20,
    show_default=True,
)
@click.option("--tags", is_flag=True, help="Show tags")
@click.option("--name", is_flag=True, help="Show names")
@click.option("--user", is_flag=True, help="Show users")
@click.option("--description", is_flag=True, help="Show description")
@click.option("--status", is_flag=True, help="Show status")
@click.option("--folder", is_flag=True, help="Show folder")
def list_runs(
    ctx,
    format: str,
    tags: bool,
    description: bool,
    user: bool,
    enumerate_: bool,
    name: bool,
    folder: bool,
    status: bool,
    **kwargs,
) -> None:
    """Retrieve runs list from Simvue server"""
    kwargs |= {"filters": kwargs.get("filters" or [])}
    runs = simvue_cli.run.get_runs_list(**kwargs)
    columns = ["id"]

    if name:
        columns.append("name")
    if folder:
        columns.append("folder")
    if tags:
        columns.append("tags")
    if user:
        columns.append("user")
    if description:
        columns.append("description")
    if status:
        columns.append("status")

    table = create_runs_display(columns, runs, plain_text=ctx.obj["plain"], enumerate_=enumerate_, format=format)
    click.echo(table)


@simvue_run.command("json")
@click.argument("run_id", required=False)
def get_run_json(run_id: str) -> None:
    """Retrieve Run information from Simvue server

    If no RUN_ID is provided the input is read from stdin
    """
    if not run_id:
        run_id = input()

    try:
        run_info = simvue_cli.run.get_run(run_id)
    except RuntimeError as e:
        error_msg = f"Failed to retrieve run '{run_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)

    click.echo(
        json.dumps(run_info)
    )


@simvue.command("purge")
@click.pass_context
def purge_simvue(ctx) -> None:
    """Remove all local Simvue files"""
    local_files_exist: bool = False
    if (user_simvue_directory := pathlib.Path().home().joinpath(".simvue")).exists():
        logger.info(f"Removing '{user_simvue_directory}'")
        shutil.rmtree(user_simvue_directory)
        local_files_exist = True
    if (global_simvue_file := pathlib.Path().home().joinpath(".simvue.ini")).exists():
        logger.info(f"Removing global Simvue configuration '{global_simvue_file}'")
        global_simvue_file.unlink()
        local_files_exist = True

    click.echo(
        "Simvue user files deleted successfully."
        if local_files_exist
        else "Nothing to do."
    )


if __name__ in "__main__":
    simvue()
