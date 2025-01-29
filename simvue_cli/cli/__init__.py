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
from simvue.api.objects import Run
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
        url = simvue_client.Client()._config.server.url
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
    user_name = user_info.get("username")
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
def create_run(
    ctx, create_only: bool, tag: tuple[str, ...] | None, **run_params
) -> None:
    """Initialise a new Simvue run"""
    run_params |= {"running": not create_only, "tags": list(tag) if tag else None}
    run_id: str = simvue_cli.actions.create_simvue_run(**run_params)

    click.echo(run_id if ctx.obj["plain"] else click.style(run_id))


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
    "count_limit",
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
        click.echo(json.dumps({k: v for k, v in run_info.items()}, indent=2))
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
    if (global_simvue_file := pathlib.Path().home().joinpath(".simvue.ini")).exists():
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


@simvue_alert.command("create")
@click.pass_context
@click.argument("name", type=SimvueName)
@click.option(
    "--abort",
    is_flag=True,
    help="Abort run if this alert is triggered",
    show_default=True,
)
@click.option(
    "--email", is_flag=True, help="Notify by email if triggered", show_default=True
)
def create_alert(ctx, name: str, abort: bool = False, email: bool = False) -> None:
    """Create a User alert"""
    result = simvue_cli.actions.create_user_alert(name, abort, email)
    alert_id = result["id"]
    click.echo(alert_id if ctx.obj["plain"] else click.style(alert_id))


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
def monitor(ctx, tag: tuple[str, ...] | None, delimiter: str, **run_params) -> None:
    """Monitor stdin for delimited lines sending as metrics"""
    metric_labels: list[str] = []
    run_params |= {"tags": list(tag) if tag else None}

    run_id: str | None = simvue_cli.actions.create_simvue_run(
        timeout=None, running=True, **run_params
    )

    if not run_id:
        raise click.Abort("Failed to create run")

    try:
        for i, line in enumerate(sys.stdin):
            line = [el for element in line.split(delimiter) if (el := element.strip())]
            if i == 0:
                metric_labels = line
                continue
            try:
                simvue_cli.actions.log_metrics(
                    run_id, dict(zip(metric_labels, [float(i) for i in line]))
                )
            except (RuntimeError, ValueError) as e:
                if ctx.obj["plain"]:
                    click.echo(e)
                else:
                    click.secho(e, fg="red", bold=True)
                sys.exit(1)
        click.echo(run_id)
    except KeyboardInterrupt as e:
        simvue_cli.actions.set_run_status(run_id, "terminated")
        raise click.Abort from e
    simvue_cli.actions.set_run_status(run_id, "completed")


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
    runs = simvue_cli.actions.get_folders_list(**kwargs)
    if not runs:
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
        runs,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


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


@simvue.group("admin")
@click.pass_context
def admin(ctx) -> None:
    """Administrator commands, requires admin access"""
    pass


@admin.group("tenant")
@click.pass_context
def tenant(ctx) -> None:
    """Manager server tenants"""


@tenant.command("add")
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
    tenant_id: str = simvue_cli.actions.create_simvue_tenant(**kwargs)
    click.echo(tenant_id if ctx.obj["plain"] else click.style(tenant_id))


@tenant.command("remove")
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
    """Remove a tenants from the Simvue server"""
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


@tenant.command("list")
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
@click.option("--max-folders", is_flag=True, help="Show maximum folders")
@click.option(
    "--max-metric-names", is_flag=True, help="Show maximum metric names per run"
)
@click.option("--max-alerts", is_flag=True, help="Show maximum alerts")
@click.option("--max-request-rate", is_flag=True, help="Show maximum request rate")
@click.option("--max-tags", is_flag=True, help="Show maximum tags")
@click.option("--max-alerts-per-run", is_flag=True, help="Show maximum alerts per run")
@click.option("--max-tags-per-run", is_flag=True, help="Show maximum tags per run")
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
    max_folders: bool,
    max_alerts: bool,
    max_request_rate: bool,
    max_tags: bool,
    max_alerts_per_run: bool,
    max_tags_per_run: bool,
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
    if max_folders:
        columns.append("max_folders")
    if max_alerts:
        columns.append("max_alerts")
    if max_request_rate:
        columns.append("max_request_rate")
    if max_tags:
        columns.append("max_tags")
    if max_alerts_per_run:
        columns.append("max_alerts_per_run")
    if max_tags_per_run:
        columns.append("max_tags_per_run")

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
def add_user(ctx, **kwargs) -> None:
    simvue_cli.actions.create_simvue_user(**kwargs)


if __name__ in "__main__":
    simvue()
