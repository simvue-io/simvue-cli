"""Simvue Tenant Commands."""

import click
import sys
import tabulate
import json

import simvue_cli.actions

from simvue_cli.cli.display import create_objects_display
from simvue_cli.validation import SimvueName
from simvue.api.objects import Tenant
from simvue.exception import ObjectNotFoundError


@click.group("tenant")
@click.pass_context
def simvue_tenant(_) -> None:
    """Manager server tenants"""


@simvue_tenant.command("json")
@click.argument("tenant_id", required=False)
@click.pass_context
def get_tenant_json(ctx, tenant_id: str) -> None:
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
        if not ctx.obj["plain"]:
            error_msg = click.style(error_msg, fg="red", bold=True)
        click.echo(error_msg)


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
    "-V",
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

    _total_tenants = simvue_cli.actions.count_tenants()

    if _total_tenants < 2:
        error_msg = "Attempting to delete single remaining tenant on server."
        if ctx.obj["plain"]:
            click.echo(error_msg)
        else:
            click.secho(error_msg, fg="red", bold=True)
        sys.exit(1)

    for tenant_id in tenant_ids:
        try:
            simvue_cli.actions.get_tenant(tenant_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"tenant '{tenant_id}' not found"
            if ctx.obj["plain"]:
                click.echo(error_msg)
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
            click.echo(response_message)
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
        columns.append("is_enabled")
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
