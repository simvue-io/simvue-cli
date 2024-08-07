"""
Simvue CLI
==========

Command line tool for interfacing with a Simvue server, this interface allows
the user to submit metrics and retrieve information from the command line.
"""
import pathlib
import shutil
import click
import click_log
import click_option_group
import logging
import tabulate

import simvue_cli.config
import simvue_cli.run

from simvue_cli.types import SimvueName, SimvueFolder, JSONType

from click_params import PUBLIC_URL

logger = logging.getLogger()
click_log.basic_config(logger)


@click.group("simvue")
@click_log.simple_verbosity_option(logger)
def simvue() -> None:
    pass


@simvue.group("config")
@click.option("--local/--global", default=True, help="Update local or global configurations", show_default=True)
@click.pass_context
def config(ctx, local: bool) -> None:
    """Configure Simvue"""
    ctx.ensure_object(dict)
    ctx.obj["local"] = local


@config.command("server.url")
@click.argument("url", type=PUBLIC_URL)
@click.pass_context
def config_set_url(ctx, url: str) -> None:
    """Update Simvue configuration URL"""
    out_file: pathlib.Path = simvue_cli.config.set_configuration_option(
        section="server",
        key="url",
        value=url,
        local=ctx.obj["local"]
    )
    click.secho(f"Wrote URL value to '{out_file}'")


@config.command("server.token")
@click.argument("token", type=str)
@click.pass_context
def config_set_token(ctx, token: str) -> None:
    """Update Simvue configuration Token"""
    out_file: pathlib.Path = simvue_cli.config.set_configuration_option(
        section="server",
        key="token",
        value=token,
        local=ctx.obj["local"]
    )
    click.secho(f"Wrote token value to '{out_file}'")


@simvue.group("run")
def simvue_run() -> None:
    """Create or retrieve Simvue runs"""
    pass


@simvue_run.command("create")
@click.option("--create-only", help="Create run but do not start it", is_flag=True, default=False)
@click_option_group.optgroup.group(
    "Run attributes",
    help="Assign properties such as metadata and labelling to this run"
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
    "--folder", type=SimvueFolder, help="Specify folder path for this run", default="/", show_default=True
)
def create_run(create_only: bool, tag: tuple[str, ...] | None, **run_params) -> None:
    """Initialise a new Simvue run"""
    run_params |= {"running": not create_only, "tags": list(tag) if tag else None}
    run_id: str = simvue_cli.run.create_simvue_run(**run_params)
    click.secho(run_id)


@simvue_run.command("close")
@click.argument("run_id", type=str)
def close_run(run_id: str) -> None:
    """Mark an active run as completed"""
    try:
        simvue_cli.run.set_run_status(run_id, "completed")
    except ValueError as e:
        click.secho(e.args[0], fg="red", bold=True)


@simvue_run.command("abort")
@click.argument("run_id", type=str)
@click.option("--reason", type=str, help="Reason for abort", default="Manual termination via CLI", show_default=True)
def abort_run(run_id: str, reason: str) -> None:
    """Abort an active run"""
    simvue_cli.run.set_run_status(run_id, "aborted", reason=reason)


@simvue_run.command("log.metrics")
@click.argument("run_id", type=str)
@click.argument("metrics", type=JSONType)
def log_metrics(run_id: str, metrics: dict) -> None:
    """Log metrics to Simvue server"""
    simvue_cli.run.log_metrics(run_id, metrics)


@simvue_run.command("list")
@click.option("-f", "--format", type=click.Choice(list(tabulate._table_formats.keys())), help="Display as table with output format", default=None)
@click.option("-n", "--count", type=int, help="Maximum number of runs to retrieve", default=20, show_default=True)
def list_runs(format: str, **kwargs) -> None:
    """Retrieve runs from Simvue server"""
    kwargs |= {"filters": kwargs.get("filters" or [])}
    runs = simvue_cli.run.get_runs_list(**kwargs)
    table_headers = [click.style(c, bold=True) for c in ("#", "id", "name")]
    contents = [[str(n)] + [i.get(c) for c in ("id", "name")] for n, i in enumerate(runs)]

    if format:
        click.echo(tabulate.tabulate(contents, headers=table_headers, tablefmt=format))
    else:
        click.echo("\n".join("\t".join(c) for c in contents))



@simvue.command("purge")
def purge_simvue() -> None:
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

    click.secho("Simvue user files deleted successfully." if local_files_exist else "Nothing to do.")


if __name__ in "__main__":
    simvue()

