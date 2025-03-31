"""
Simvue CLI
==========

Command line tool for interfacing with a Simvue server, this interface allows
the user to submit metrics and retrieve information from the command line.
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import pathlib
import sys
import shutil
import click
import json
import time
import click_log
import click_option_group
import datetime
import logging
import contextlib
import importlib.metadata

import tabulate
import requests
import simvue as simvue_client
from simvue.api.objects import Alert, Run, Folder, S3Storage, Tag, Storage
from simvue.api.objects.administrator import User, Tenant
from simvue.exception import ObjectNotFoundError

import simvue_cli.config
import simvue_cli.actions
import simvue_cli.server

from simvue_cli.cli.display import create_objects_display, SIMVUE_LOGO
from simvue_cli.validation import (
    SimvueName,
    SimvueFolder,
    JSONType,
    Email,
    FullName,
    UserName,
)

from click_params import PUBLIC_URL

logging.getLogger("simvue").setLevel(logging.ERROR)
logger = logging.getLogger()
click_log.basic_config(logger)


@click.group("simvue-cli")
@click_log.simple_verbosity_option(logger)
@click.version_option()
@click.option(
    "--plain", help="Run without color/formatting", default=False, is_flag=True
)
@click.pass_context
def simvue(ctx, plain: bool) -> None:
    """Simvue CLI for interacting with a Simvue server instance

    Provides functionality for the retrieval, creation and modification of server objects
    """
    ctx.ensure_object(dict)
    ctx.obj["plain"] = plain


@simvue.command("ping")
@click.option(
    "-t",
    "--timeout",
    help="Timeout the command after n seconds",
    default=None,
    type=int,
)
def ping_server(timeout: int | None) -> None:
    """Ping the Simvue server"""
    successful_pings: int = 0
    with contextlib.suppress(KeyboardInterrupt):
        url = simvue_client.Client()._user_config.server.url
        ip_address = simvue_cli.server.get_ip_of_url(url)
        counter: int = 0
        while True:
            if timeout and counter > timeout:
                return
            start_time = time.time()
            try:
                server_version: int | str = simvue_cli.actions.get_server_version()
                if (
                    status_code := 200
                    if isinstance(server_version, str)
                    else server_version
                ) != 200:
                    raise RuntimeError
                successful_pings += 1
                end_time = time.time()  # Record the end time
                elapsed_time = (end_time - start_time) * 1000  # Convert to milliseconds
                click.secho(
                    f"Reply from {url} ({ip_address}): status_code={status_code}, time={elapsed_time:.2f}ms"
                )
            except (requests.ConnectionError, requests.Timeout, RuntimeError):
                click.secho(
                    f"Reply from {url} ({ip_address}): status_code={status_code}, error"
                )

            time.sleep(1)
            counter += 1


@simvue.command("whoami")
@click.option("-u", "--user", help="print only the user name", default=False)
@click.option("-t", "--tenant", help="print only the tenant", default=False)
def whoami(user: bool, tenant: bool) -> None:
    """Retrieve current user information"""
    if user and tenant:
        click.secho("cannot print 'only' with more than one choice")
        raise click.Abort
    user_info = simvue_cli.actions.user_info()
    user_name = user_info.get("user")
    tenant_info = user_info.get("tenant")
    if user:
        click.secho(user_name)
    elif tenant:
        click.secho(tenant_info)
    else:
        click.secho(f"{user_name}({tenant_info})")


@simvue.command("about")
@click.pass_context
def about_simvue(ctx) -> None:
    """Display full information on Simvue instance"""
    width = shutil.get_terminal_size().columns
    click.echo(
        "\n".join(f"{'\t' * int(0.015 * width)}{r}" for r in SIMVUE_LOGO.split("\n"))
    )
    click.echo(f"\n{width * '='}\n")
    click.echo(f"\n{'\t' * int(0.04 * width)} Provided under the Apache-2.0 License")
    click.echo(
        f"{'\t' * int(0.04 * width)}© Copyright {datetime.datetime.now().strftime('%Y')} Simvue Development Team\n"
    )
    out_table: list[list[str]] = []
    with contextlib.suppress(importlib.metadata.PackageNotFoundError):
        out_table.append(
            ["CLI Version: ", importlib.metadata.version(simvue_cli.__name__)]
        )
    with contextlib.suppress(importlib.metadata.PackageNotFoundError):
        out_table.append(
            ["Python API Version: ", importlib.metadata.version(simvue_client.__name__)]
        )
    with contextlib.suppress(Exception):
        server_version: int | str = simvue_cli.actions.get_server_version()
        if isinstance(server_version, int):
            raise RuntimeError
        out_table.append(["Server Version: ", server_version])
    click.echo(
        "\n".join(
            f"{'\t' * int(0.045 * width)}{r}"
            for r in tabulate.tabulate(out_table, tablefmt="plain")
            .__str__()
            .split("\n")
        )
    )
    click.echo(f"\n{width * '='}\n")


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
@click.option(
    "--timeout",
    help="Set a timeout in seconds after which this run will register as 'lost'",
    default=None,
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
@click_option_group.optgroup.option(
    "--retention",
    type=int,
    help="Specify retention period",
    default=None,
)
@click_option_group.optgroup.option(
    "--environment", is_flag=True, default=False, help="Include environment metadata"
)
def create_run(
    ctx, create_only: bool, tag: tuple[str, ...] | None, **run_params
) -> None:
    """Initialise a new Simvue run"""
    run_params |= {"running": not create_only, "tags": list(tag) if tag else None}
    run: Run = simvue_cli.actions.create_simvue_run(**run_params)

    click.echo(run.id if ctx.obj["plain"] else click.style(run.id))


@simvue_run.command("remove")
@click.pass_context
@click.argument("run_ids", type=str, nargs=-1, required=False)
@click.option(
    "-i",
    "--interactive",
    help="Prompt for confirmation on removal",
    type=bool,
    default=False,
    is_flag=True,
)
def delete_run(ctx, run_ids: list[str] | None, interactive: bool) -> None:
    """Remove a runs from the Simvue server"""
    if not run_ids:
        run_ids = []
        for line in sys.stdin:
            if not line.strip():
                continue
            run_ids += [k.strip() for k in line.split(" ")]

    for run_id in run_ids:
        try:
            simvue_cli.actions.get_run(run_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"Run '{run_id}' not found"
            if ctx.obj["plain"]:
                print(error_msg)
            else:
                click.secho(error_msg, fg="red", bold=True)
            sys.exit(1)

        if interactive:
            remove = click.confirm(f"Remove run '{run_id}'?")
            if not remove:
                continue

        try:
            simvue_cli.actions.delete_run(run_id)
        except ValueError as e:
            click.echo(
                e.args[0]
                if ctx.obj["plain"]
                else click.style(e.args[0], fg="red", bold=True)
            )
            sys.exit(1)

        response_message = f"Run '{run_id}' removed successfully."

        if ctx.obj["plain"]:
            print(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue_run.command("close")
@click.pass_context
@click.argument("run_id", type=str)
def close_run(ctx, run_id: str) -> None:
    """Mark an active run as completed"""
    if not (simvue_cli.actions.get_run(run_id)):
        error_msg = f"Run '{run_id}' not found"
        if ctx.obj["plain"]:
            print(error_msg)
        else:
            click.secho(error_msg, fg="red", bold=True)
        sys.exit(1)
    try:
        simvue_cli.actions.set_run_status(run_id, "completed")
    except ValueError as e:
        click.echo(
            e.args[0]
            if ctx.obj["plain"]
            else click.style(e.args[0], fg="red", bold=True)
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
    if not (simvue_cli.actions.get_run(run_id)):
        error_msg = f"Run '{run_id}' not found"
        if ctx.obj["plain"]:
            print(error_msg)
        else:
            click.secho(error_msg, fg="red", bold=True)
        sys.exit(1)
    simvue_cli.actions.set_run_status(run_id, "terminated", reason=reason)


@simvue_run.command("log.metrics")
@click.argument("run_id", type=str)
@click.argument("metrics", type=JSONType)
def log_metrics(run_id: str, metrics: dict) -> None:
    """Log metrics to Simvue server"""
    simvue_cli.actions.log_metrics(run_id, metrics)


@simvue_run.command("log.event")
@click.argument("run_id", type=str)
@click.argument("event_message", type=str)
def log_event(run_id: str, event_message: str) -> None:
    """Log event to Simvue server"""
    simvue_cli.actions.log_event(run_id, event_message)


@simvue_run.command("metadata")
@click.argument("run_id", type=str)
@click.argument("metadata", type=JSONType)
def update_metadata(run_id: str, metadata: dict) -> None:
    """Update metadata for a run on the Simvue server"""
    simvue_cli.actions.update_metadata(run_id, metadata)


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
@click.option("--created", is_flag=True, help="Show created timestamp")
@click.option("--description", is_flag=True, help="Show description")
@click.option("--status", is_flag=True, help="Show status")
@click.option("--folder", is_flag=True, help="Show folder")
@click.option(
    "--sort-by",
    help="Specify columns to sort by",
    multiple=True,
    default=["created"],
    type=click.Choice(["created", "started", "endtime", "modified", "name"]),
    show_default=True,
)
@click.option("--reverse", help="Reverse ordering", default=False, is_flag=True)
def list_runs(
    ctx,
    format: str,
    tags: bool,
    description: bool,
    user: bool,
    created: bool,
    enumerate_: bool,
    name: bool,
    folder: bool,
    status: bool,
    **kwargs,
) -> None:
    """Retrieve runs list from Simvue server"""
    kwargs |= {"filters": kwargs.get("filters" or [])}
    runs = simvue_cli.actions.get_runs_list(**kwargs)
    columns = ["id"]

    if created:
        columns.append("created")
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

    table = create_objects_display(
        columns, runs, plain_text=ctx.obj["plain"], enumerate_=enumerate_, format=format
    )
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
        run: Run = simvue_cli.actions.get_run(run_id)
        run_info = run.to_dict()
        click.echo(json.dumps(dict(run_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve run '{run_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)


@simvue.command("purge")
@click.pass_context
def purge_simvue(ctx) -> None:
    """Remove all local Simvue files"""
    local_files_exist: bool = False
    if (user_simvue_directory := pathlib.Path().home().joinpath(".simvue")).exists():
        logger.info(f"Removing '{user_simvue_directory}'")
        shutil.rmtree(user_simvue_directory)
        local_files_exist = True
    if (global_simvue_file := pathlib.Path().home().joinpath(".simvue.toml")).exists():
        logger.info(f"Removing global Simvue configuration '{global_simvue_file}'")
        global_simvue_file.unlink()
        local_files_exist = True

    click.echo(
        "Simvue user files deleted successfully."
        if local_files_exist
        else "Nothing to do."
    )


@simvue.group("alert")
@click.pass_context
def simvue_alert(ctx) -> None:
    """Create and list Simvue alerts"""
    pass


@simvue_alert.command("list")
@click.pass_context
@click.option(
    "--format",
    "table_format",
    type=click.Choice(list(tabulate._table_formats.keys())),
    help="Display as table with output format",
    default=None,
)
@click.option(
    "--enumerate",
    "enumerate_",
    is_flag=True,
    help="Show counter next to alerts",
    default=False,
    show_default=True,
)
@click.option(
    "--offset",
    type=int,
    help="Start index for results",
    default=None,
    show_default=None,
)
@click.option(
    "--count",
    type=int,
    help="Maximum number of alerts to retrieve",
    default=20,
    show_default=True,
)
@click.option("--path", is_flag=True, help="Show path")
@click.option("--run-tags", is_flag=True, help="Show tags")
@click.option("--auto", is_flag=True, help="Show if run tag auto-assign is enabled")
@click.option("--notification", is_flag=True, help="Show notification setting")
@click.option("--created", is_flag=True, help="Show created timestamp")
@click.option("--source", is_flag=True, help="Show alert source")
@click.option("--enabled", is_flag=True, help="Show if alert enabled")
@click.option("--abort", is_flag=True, help="Show alert if alert can abort runs")
@click.option("--name", is_flag=True, help="Show names")
@click.option("--description", is_flag=True, help="Show description")
@click.option(
    "--sort-by",
    help="Specify columns to sort by",
    multiple=True,
    default=["created"],
    type=click.Choice(["created", "name"]),
    show_default=True,
)
@click.option("--reverse", help="Reverse ordering", default=False, is_flag=True)
def alert_list(
    ctx,
    table_format: str,
    enumerate_: bool,
    run_tags: bool,
    name: bool,
    auto: bool,
    notification: bool,
    source: bool,
    enabled: bool,
    description: bool,
    created: bool,
    **kwargs,
) -> None:
    """Retrieve alerts list from Simvue server"""
    kwargs |= {"filters": kwargs.get("filters" or [])}
    alerts = simvue_cli.actions.get_alerts_list(**kwargs)
    if not alerts:
        return
    columns = ["id"]

    if name:
        columns.append("name")
    if created:
        columns.append("created")
    if run_tags:
        columns.append("run_tags")
    if description:
        columns.append("description")
    if notification:
        columns.append("notification")
    if enabled:
        columns.append("enabled")
    if auto:
        columns.append("auto")
    if source:
        columns.append("source")

    table = create_objects_display(
        columns,
        alerts,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@simvue_alert.command("create")
@click.pass_context
@click.argument("name", type=SimvueName)
@click.option(
    "--abort",
    is_flag=True,
    help="Abort run if this alert is triggered",
    show_default=True,
)
@click.option("--description", default=None, help="Description for this alert.")
@click.option(
    "--email", is_flag=True, help="Notify by email if triggered", show_default=True
)
def create_alert(
    ctx,
    name: str,
    abort: bool = False,
    email: bool = False,
    description: str | None = None,
) -> None:
    """Create a User alert"""
    result = simvue_cli.actions.create_user_alert(
        name=name, trigger_abort=abort, email_notify=email, description=description
    )
    alert_id = result.id
    click.echo(alert_id if ctx.obj["plain"] else click.style(alert_id))


@simvue_alert.command("remove")
@click.pass_context
@click.argument("alert_ids", type=str, nargs=-1, required=False)
@click.option(
    "-i",
    "--interactive",
    help="Prompt for confirmation on removal",
    type=bool,
    default=False,
    is_flag=True,
)
def delete_alert(ctx, alert_ids: list[str] | None, interactive: bool) -> None:
    """Remove a alert from the Simvue server"""
    if not alert_ids:
        alert_ids = []
        for line in sys.stdin:
            if not line.strip():
                continue
            alert_ids += [k.strip() for k in line.split(" ")]

    for alert_id in alert_ids:
        try:
            simvue_cli.actions.get_alert(alert_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"alert '{alert_id}' not found"
            if ctx.obj["plain"]:
                print(error_msg)
            else:
                click.secho(error_msg, fg="red", bold=True)
            sys.exit(1)

        if interactive:
            remove = click.confirm(f"Remove alert '{alert_id}'?")
            if not remove:
                continue

        try:
            simvue_cli.actions.delete_alert(alert_id)
        except ValueError as e:
            click.echo(
                e.args[0]
                if ctx.obj["plain"]
                else click.style(e.args[0], fg="red", bold=True)
            )
            sys.exit(1)

        response_message = f"alert '{alert_id}' removed successfully."

        if ctx.obj["plain"]:
            print(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue_alert.command("json")
@click.argument("alert_id", required=False)
def get_alert_json(alert_id: str) -> None:
    """Retrieve alert information from Simvue server

    If no alert ID is provided the input is read from stdin
    """
    if not alert_id:
        alert_id = input()

    try:
        alert: Alert = simvue_cli.actions.get_alert(alert_id)
        alert_info = alert.to_dict()
        click.echo(json.dumps(dict(alert_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve alert '{alert_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)


@simvue.command("monitor")
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
@click_option_group.optgroup.option(
    "--retention",
    type=int,
    help="Specify retention period",
    default=None,
)
@click.pass_context
@click.option(
    "--delimiter",
    "-d",
    help="File row delimiter",
    default=None,
    show_default=True,
    type=str,
)
@click.option(
    "--environment", help="Include environment in metadata", is_flag=True, default=False
)
def monitor(ctx, tag: tuple[str, ...] | None, delimiter: str, **run_params) -> None:
    """Monitor stdin for delimited lines sending as metrics"""
    metric_labels: list[str] = []
    run_params |= {"tags": list(tag) if tag else None}

    run: Run | None = simvue_cli.actions.create_simvue_run(
        timeout=None, running=True, **run_params
    )

    if not run:
        raise click.Abort("Failed to create run")

    try:
        for i, line in enumerate(sys.stdin):
            line = [el for element in line.split(delimiter) if (el := element.strip())]
            if i == 0:
                metric_labels = line
                continue
            try:
                simvue_cli.actions.log_metrics(
                    run.id, dict(zip(metric_labels, [float(i) for i in line]))
                )
            except (RuntimeError, ValueError) as e:
                if ctx.obj["plain"]:
                    click.echo(e)
                else:
                    click.secho(e, fg="red", bold=True)
                sys.exit(1)
        click.echo(run.id)
    except KeyboardInterrupt as e:
        simvue_cli.actions.set_run_status(run.id, "terminated")
        raise click.Abort from e
    simvue_cli.actions.set_run_status(run.id, "completed")


@simvue.group("folder")
@click.pass_context
def simvue_folder(ctx) -> None:
    """Create or retrieve Simvue folders"""
    pass


@simvue_folder.command("list")
@click.pass_context
@click.option(
    "--format",
    "table_format",
    type=click.Choice(list(tabulate._table_formats.keys())),
    help="Display as table with output format",
    default=None,
)
@click.option(
    "--enumerate",
    "enumerate_",
    is_flag=True,
    help="Show counter next to folders",
    default=False,
    show_default=True,
)
@click.option(
    "--count",
    type=int,
    help="Maximum number of folders to retrieve",
    default=20,
    show_default=True,
)
@click.option("--path", is_flag=True, help="Show path")
@click.option("--tags", is_flag=True, help="Show tags")
@click.option("--created", is_flag=True, help="Show created timestamp")
@click.option("--name", is_flag=True, help="Show names")
@click.option("--description", is_flag=True, help="Show description")
@click.option(
    "--sort-by",
    help="Specify columns to sort by",
    multiple=True,
    default=["created"],
    type=click.Choice(["created", "modified", "path"]),
    show_default=True,
)
@click.option("--reverse", help="Reverse ordering", default=False, is_flag=True)
def folder_list(
    ctx,
    table_format: str,
    enumerate_: bool,
    path: bool,
    tags: bool,
    name: bool,
    created: bool,
    description: bool,
    **kwargs,
) -> None:
    """Retrieve folders list from Simvue server"""
    kwargs |= {"filters": kwargs.get("filters" or [])}
    folders = simvue_cli.actions.get_folders_list(**kwargs)
    if not folders:
        return
    columns = ["id"]

    if created:
        columns.append("created")
    if path:
        columns.append("path")
    if name:
        columns.append("name")
    if tags:
        columns.append("tags")
    if description:
        columns.append("description")

    table = create_objects_display(
        columns,
        folders,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@simvue_folder.command("json")
@click.argument("folder_id", required=False)
def get_folder_json(folder_id: str) -> None:
    """Retrieve folder information from Simvue server

    If no folder_ID is provided the input is read from stdin
    """
    if not folder_id:
        folder_id = input()

    try:
        folder: Folder = simvue_cli.actions.get_folder(folder_id)
        folder_info = folder.to_dict()
        click.echo(json.dumps(dict(folder_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve folder '{folder_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)


@simvue.group("tag")
@click.pass_context
def simvue_tag(ctx) -> None:
    """Create or retrieve Simvue runs"""
    pass


@simvue_tag.command("list")
@click.pass_context
@click.option(
    "--format",
    "table_format",
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
@click.option("--created", is_flag=True, help="Show created timestamp")
@click.option(
    "--count",
    type=int,
    help="Maximum number of runs to retrieve",
    default=20,
    show_default=True,
)
@click.option("--name", is_flag=True, help="Show names")
@click.option("--color", is_flag=True, help="Show hex colors")
@click.option(
    "--sort-by",
    help="Specify columns to sort by",
    multiple=True,
    default=["created"],
    type=click.Choice(["created", "name"]),
    show_default=True,
)
@click.option("--reverse", help="Reverse ordering", default=False, is_flag=True)
def tag_list(
    ctx,
    count: int,
    enumerate_: bool,
    created: bool,
    table_format: str | None,
    name: bool,
    color: bool,
    **kwargs,
) -> None:
    tags = simvue_cli.actions.get_tag_list(**kwargs)
    if not tags:
        return
    columns = ["id"]

    if created:
        columns.append("created")

    if name:
        columns.append("name")

    if color:
        columns.append("colour")

    table = create_objects_display(
        columns,
        tags,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@simvue_tag.command("json")
@click.argument("tag_id", required=False)
def get_tag_json(tag_id: str) -> None:
    """Retrieve tag information from Simvue server

    If no tag_ID is provided the input is read from stdin
    """
    if not tag_id:
        tag_id = input()

    try:
        tag: Tag = simvue_cli.actions.get_tag(tag_id)
        tag_info = tag.to_dict()
        click.echo(json.dumps(dict(tag_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve tag '{tag_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)


@simvue.group("admin")
@click.pass_context
def admin(ctx) -> None:
    """Administrator commands, requires admin access"""
    pass


@admin.group("tenant")
@click.pass_context
def simvue_tenant(ctx) -> None:
    """Manager server tenants"""


@simvue_tenant.command("json")
@click.argument("tenant_id", required=False)
def get_tenant_json(tenant_id: str) -> None:
    """Retrieve tenant information from Simvue server

    If no tenant ID is provided the input is read from stdin
    """
    if not tenant_id:
        tenant_id = input()

    try:
        tenant: Tenant = simvue_cli.actions.get_tenant(tenant_id)
        tenant_info = tenant.to_dict()
        click.echo(json.dumps(dict(tenant_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve tenant '{tenant_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)


@simvue_tenant.command("add")
@click.pass_context
@click.argument("name", type=SimvueName)
@click.option(
    "--disabled", is_flag=True, default=False, help="disable this tenant on creation"
)
@click.option(
    "--max-runs",
    "-m",
    default=None,
    type=click.IntRange(min=1, max_open=True),
    help="run quota for this tenant",
)
@click.option(
    "--max-request-rate",
    "-r",
    default=None,
    type=click.IntRange(min=1, max_open=True),
    help="request rate limit for this tenant",
)
@click.option(
    "--max-data-volume",
    "-v",
    default=None,
    type=click.IntRange(min=1, max_open=True),
    help="data storage limit for this tenant",
)
def add_tenant(ctx, **kwargs) -> None:
    """Add a tenant to the Simvue server"""
    tenant: Tenant = simvue_cli.actions.create_simvue_tenant(**kwargs)
    click.echo(tenant.id if ctx.obj["plain"] else click.style(tenant.id))


@simvue_tenant.command("remove")
@click.pass_context
@click.argument("tenant_ids", type=str, nargs=-1, required=False)
@click.option(
    "-i",
    "--interactive",
    help="Prompt for confirmation on removal",
    type=bool,
    default=False,
    is_flag=True,
)
def delete_tenant(ctx, tenant_ids: list[str] | None, interactive: bool) -> None:
    """Remove a tenant from the Simvue server"""
    if not tenant_ids:
        tenant_ids = []
        for line in sys.stdin:
            if not line.strip():
                continue
            tenant_ids += [k.strip() for k in line.split(" ")]

    for tenant_id in tenant_ids:
        try:
            simvue_cli.actions.get_tenant(tenant_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"tenant '{tenant_id}' not found"
            if ctx.obj["plain"]:
                print(error_msg)
            else:
                click.secho(error_msg, fg="red", bold=True)
            sys.exit(1)

        if interactive:
            remove = click.confirm(f"Remove tenant '{tenant_id}'?")
            if not remove:
                continue

        try:
            simvue_cli.actions.delete_tenant(tenant_id)
        except ValueError as e:
            click.echo(
                e.args[0]
                if ctx.obj["plain"]
                else click.style(e.args[0], fg="red", bold=True)
            )
            sys.exit(1)

        response_message = f"tenant '{tenant_id}' removed successfully."

        if ctx.obj["plain"]:
            print(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue_tenant.command("list")
@click.pass_context
@click.option(
    "--format",
    "table_format",
    type=click.Choice(list(tabulate._table_formats.keys())),
    help="Display as table with output format",
    default=None,
)
@click.option(
    "--enumerate",
    "enumerate_",
    is_flag=True,
    help="Show counter next to tenants",
    default=False,
    show_default=True,
)
@click.option(
    "--count",
    type=int,
    help="Maximum number of tenants to retrieve",
    default=20,
    show_default=True,
)
@click.option("--max-runs", is_flag=True, help="Show max runs")
@click.option("--max-data-volume", is_flag=True, help="Show maximum data volume")
@click.option("--max-request-rate", is_flag=True, help="Show maximum request rate")
@click.option("--created", is_flag=True, help="Show created timestamp")
@click.option("--name", is_flag=True, help="Show names")
@click.option("--enabled", is_flag=True, help="Show if enabled")
def tenant_list(
    ctx,
    table_format: str,
    enumerate_: bool,
    count: int,
    max_runs: bool,
    max_data_volume: bool,
    max_request_rate: bool,
    created: bool,
    name: bool,
    enabled: bool,
    **kwargs,
) -> None:
    """Retrieve tenants list from Simvue server"""
    runs = simvue_cli.actions.get_tenants_list(**kwargs)
    if not runs:
        return
    columns = ["id"]

    if created:
        columns.append("created")
    if name:
        columns.append("name")
    if enabled:
        columns.append("enabled")
    if max_runs:
        columns.append("max_runs")
    if max_data_volume:
        columns.append("max_data_volume")
    if max_request_rate:
        columns.append("max_request_rate")

    table = create_objects_display(
        columns,
        runs,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@admin.group("user")
@click.pass_context
def user(ctx) -> None:
    """Manage server users"""
    pass


@user.command("list")
@click.option(
    "--format",
    "table_format",
    type=click.Choice(list(tabulate._table_formats.keys())),
    help="Display as table with output format",
    default=None,
)
@click.option(
    "--enumerate",
    "enumerate_",
    is_flag=True,
    help="Show counter next to tenants",
    default=False,
    show_default=True,
)
@click.option(
    "--count",
    type=int,
    help="Maximum number of tenants to retrieve",
    default=20,
    show_default=True,
)
@click.option("--username", is_flag=True, default=False, help="display username")
@click.option("--email", is_flag=True, default=False, help="display user email")
@click.option("--full-name", is_flag=True, default=False, help="display user full name")
@click.option("--admin", is_flag=True, default=False, help="show admin status")
@click.option("--manager", is_flag=True, default=False, help="show manager status")
@click.option("--enabled", is_flag=True, default=False, help="show enabled status")
@click.option(
    "--read-only", is_flag=True, default=False, help="show user read only status"
)
@click.option(
    "--deleted", is_flag=True, default=False, help="show user deletion status"
)
@click.pass_context
def list_user(
    ctx,
    enumerate_: bool,
    count: int,
    table_format: str | None,
    username: bool,
    email: bool,
    full_name: bool,
    admin: bool,
    manager: bool,
    enabled: bool,
    read_only: bool,
    deleted: bool,
    **kwargs,
) -> None:
    """Retrieve user list from Simvue server"""
    users = simvue_cli.actions.get_users_list(**kwargs)
    if not users:
        return

    columns = ["id"]

    if username:
        columns.append("username")
    if email:
        columns.append("email")
    if full_name:
        columns.append("fullname")
    if admin:
        columns.append("admin")
    if manager:
        columns.append("manager")
    if enabled:
        columns.append("enabled")
    if read_only:
        columns.append("readonly")
    if deleted:
        columns.append("deleted")

    table = create_objects_display(
        columns,
        users,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@user.command("json")
@click.argument("user_id", required=False)
def get_user_json(user_id: str) -> None:
    """Retrieve user information from Simvue server

    If no user ID is provided the input is read from stdin
    """
    if not user_id:
        user_id = input()

    try:
        user: User = simvue_cli.actions.get_user(user_id)
        user_info = user.to_dict()
        click.echo(json.dumps(dict(user_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve user '{user_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)


@user.command("add")
@click.pass_context
@click.argument("username", type=UserName)
@click.option(
    "--email",
    "-e",
    required=True,
    help="registration email for user",
    type=Email,
)
@click.option(
    "--full-name",
    "-n",
    required=True,
    help="full name of this user",
    type=FullName,
)
@click.option(
    "--tenant", "-t", required=True, help="tenant group to assign this user to"
)
@click.option(
    "--manager", is_flag=True, default=False, help="assign manager role to this user"
)
@click.option(
    "--admin",
    is_flag=True,
    default=False,
    help="assign administrator role to this user",
)
@click.option(
    "--disabled", is_flag=True, default=False, help="disable this user on creation"
)
@click.option(
    "--read-only", is_flag=True, default=False, help="give this user only read access"
)
@click.option("--welcome", is_flag=True, default=False, help="display welcome message")
def add_user(ctx, **kwargs) -> None:
    user: User = simvue_cli.actions.create_simvue_user(**kwargs)
    click.echo(user.id if ctx.obj["plain"] else click.style(user.id))


@user.command("remove")
@click.pass_context
@click.argument("user_ids", type=str, nargs=-1, required=False)
@click.option(
    "-i",
    "--interactive",
    help="Prompt for confirmation on removal",
    type=bool,
    default=False,
    is_flag=True,
)
def delete_user(ctx, user_ids: list[str] | None, interactive: bool) -> None:
    """Remove a user from the Simvue server"""
    if not user_ids:
        user_ids = []
        for line in sys.stdin:
            if not line.strip():
                continue
            user_ids += [k.strip() for k in line.split(" ")]

    for user_id in user_ids:
        try:
            simvue_cli.actions.get_user(user_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"user '{user_id}' not found"
            if ctx.obj["plain"]:
                print(error_msg)
            else:
                click.secho(error_msg, fg="red", bold=True)
            sys.exit(1)

        if interactive:
            remove = click.confirm(f"Remove user '{user_id}'?")
            if not remove:
                continue

        try:
            simvue_cli.actions.delete_user(user_id)
        except ValueError as e:
            click.echo(
                e.args[0]
                if ctx.obj["plain"]
                else click.style(e.args[0], fg="red", bold=True)
            )
            sys.exit(1)

        response_message = f"user '{user_id}' removed successfully."

        if ctx.obj["plain"]:
            print(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue.group("storage")
@click.pass_context
def simvue_storage(ctx):
    """View and manage Simvue storages"""
    pass


@simvue_storage.group("add")
@click.pass_context
def simvue_storage_add(ctx) -> None:
    """Add a new Simvue storage instance to the server."""
    pass


@simvue_storage_add.command("s3")
@click.argument("name")
@click.option(
    "--disable-check",
    is_flag=True,
    default=False,
    help="Disable checking of storage system.",
    show_default=True,
)
@click.option(
    "--region-name",
    help="Name of the region associated with this storage.",
    required=True,
)
@click.option(
    "--endpoint-url", help="Endpoint defining the S3 upload URL", required=True
)
@click.option("--access-key-id", help="Access key identifier.", required=True)
@click.option(
    "--access-key-file",
    help="File containing secret access key",
    required=True,
    type=click.File(),
)
@click.option(
    "--bucket", help="The bucket associated with this storage.", required=True
)
@click.option(
    "--block-tenant",
    is_flag=True,
    default=False,
    help="Disable access by current Tenant.",
    show_default=True,
)
@click.option(
    "--default",
    is_flag=True,
    default=False,
    help="Set this storage to be the default.",
    show_default=True,
)
@click.option(
    "--disable",
    is_flag=True,
    default=False,
    help="Disable this storage on creation.",
    show_default=True,
)
@click.pass_context
def add_s3_storage(ctx, **kwargs) -> None:
    storage: S3Storage = simvue_cli.actions.create_simvue_s3_storage(**kwargs)
    click.echo(storage.id if ctx.obj["plain"] else click.style(storage.id))


@simvue_storage.command("json")
@click.pass_context
@click.argument("storage_id", required=False)
def get_storage_json(ctx, storage_id: str) -> None:
    """Retrieve storage information from Simvue server

    If no storage_ID is provided the input is read from stdin
    """
    if not storage_id:
        storage_id = input()

    try:
        storage: Storage = simvue_cli.actions.get_storage(storage_id)
        storage_info = storage.to_dict()
        click.echo(json.dumps(dict(storage_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve storage '{storage_id}': {e.args[0]}"
        click.echo(error_msg, fg="red", bold=True)


@simvue_storage.command("remove")
@click.pass_context
@click.argument("storage_ids", type=str, nargs=-1, required=False)
@click.option(
    "-i",
    "--interactive",
    help="Prompt for confirmation on removal",
    type=bool,
    default=False,
    is_flag=True,
)
def delete_storage(ctx, storage_ids: list[str] | None, interactive: bool) -> None:
    """Remove a storage from the Simvue server"""
    if not storage_ids:
        storage_ids = []
        for line in sys.stdin:
            if not line.strip():
                continue
            storage_ids += [k.strip() for k in line.split(" ")]

    for storage_id in storage_ids:
        try:
            simvue_cli.actions.get_storage(storage_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"storage '{storage_id}' not found"
            if ctx.obj["plain"]:
                print(error_msg)
            else:
                click.secho(error_msg, fg="red", bold=True)
            sys.exit(1)

        if interactive:
            remove = click.confirm(f"Remove storage '{storage_id}'?")
            if not remove:
                continue

        try:
            simvue_cli.actions.delete_storage(storage_id)
        except ValueError as e:
            click.echo(
                e.args[0]
                if ctx.obj["plain"]
                else click.style(e.args[0], fg="red", bold=True)
            )
            sys.exit(1)

        response_message = f"storage '{storage_id}' removed successfully."

        if ctx.obj["plain"]:
            print(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue_storage.command("list")
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
    help="Show counter next to storages",
    default=False,
    show_default=True,
)
@click.option(
    "--count",
    type=int,
    help="Maximum number of storages to retrieve",
    default=20,
    show_default=True,
)
@click.option("--name", is_flag=True, help="Show names")
@click.option("--backend", is_flag=True, help="Show backend")
@click.option("--created", is_flag=True, help="Show created timestamp")
@click.option("--default", is_flag=True, help="Show if default storage")
@click.option("--tenant-usable", is_flag=True, help="Show if usable by current tenant")
@click.option("--enabled", is_flag=True, help="Show if storage is enabled")
def list_storages(
    ctx,
    format: str,
    backend: bool,
    tenant_usable: bool,
    default: bool,
    enabled: bool,
    created: bool,
    enumerate_: bool,
    name: bool,
    **kwargs,
) -> None:
    """Retrieve storages list from Simvue server"""
    storages = simvue_cli.actions.get_storages_list(**kwargs)
    columns = ["id"]

    if created:
        columns.append("created")
    if name:
        columns.append("name")
    if backend:
        columns.append("backend")
    if tenant_usable:
        columns.append("tenant_usable")
    if default:
        columns.append("default")

    table = create_objects_display(
        columns,
        storages,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=format,
    )
    click.echo(table)


@simvue.command("venv")
@click.pass_context
@click.option(
    "--language",
    required=True,
    help="Specify target language",
    type=click.Choice(["python", "rust", "julia", "nodejs"]),
)
@click.option("--run", required=True, help="ID of run to clone environment from")
@click.option(
    "--allow-existing",
    is_flag=True,
    help="Install dependencies in an existing environment",
)
@click.argument("venv_directory", type=click.Path(exists=False))
def venv_setup(ctx, **kwargs) -> None:
    """Initialise virtual environments from run metadata."""
    try:
        simvue_cli.actions.create_environment(**kwargs)
    except (FileExistsError, RuntimeError) as e:
        error_msg = e.args[0]
        if ctx.obj["plain"]:
            print(error_msg)
        else:
            click.secho(error_msg, fg="red", bold=True)
        sys.exit(1)


@simvue.group("artifact")
@click.pass_context
def simvue_artifact(ctx):
    """View and manage Simvue artifacts"""
    pass


@simvue_artifact.command("list")
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
@click.option(
    "--original-path",
    is_flag=True,
    help="Show original path of artifact",
    default=False,
)
@click.option(
    "--storage", is_flag=True, help="Show storage ID of artifact", default=False
)
@click.option(
    "--mime-type", is_flag=True, help="Show MIME type of artifact", default=False
)
@click.option("--created", is_flag=True, help="Show created timestamp")
@click.option("--user", is_flag=True, help="Show artifact user UUID")
@click.option("--download-url", is_flag=True, help="Show artifact download URL")
@click.option("--uploaded", is_flag=True, help="Show artifact upload status")
@click.option("--checksum", is_flag=True, help="Show artifact checksum")
@click.option("--name", is_flag=True, help="Show artifact name")
@click.option("--size", is_flag=True, help="Show artifact size")
@click.option(
    "--sort-by",
    help="Specify columns to sort by",
    multiple=True,
    default=["created"],
    type=click.Choice(["created", "name"]),
    show_default=True,
)
@click.option("--reverse", help="Reverse ordering", default=False, is_flag=True)
@click.pass_context
def artifact_list(
    ctx,
    format_: str,
    enumerate_: bool,
    original_path: bool,
    storage: bool,
    mime_type: bool,
    created: bool,
    user: bool,
    download_url: bool,
    uploaded: bool,
    name: bool,
    size: bool,
    **kwargs,
) -> None:
    """Retrieve artifact list from Simvue server"""
    storages = simvue_cli.actions.get_artifacts_list(**kwargs)
    columns = ["id"]

    if created:
        columns.append("created")
    if name:
        columns.append("name")
    if size:
        columns.append("size")
    if original_path:
        columns.append("original_path")
    if storage:
        columns.append("storage")
    if uploaded:
        columns.append("uploaded")
    if mime_type:
        columns.append("mime_type")
    if user:
        columns.append("user")
    if download_url:
        columns.append("download_url")

    table = create_objects_display(
        columns,
        storages,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=format,
    )
    click.echo(table)


if __name__ in "__main__":
    simvue()
