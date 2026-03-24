"""Simvue Storage Commands."""

import click
import json
import sys
from simvue.api.objects import S3Storage
import tabulate
import simvue_cli.actions

from simvue_cli.cli.display import create_objects_display
from simvue.api.objects.storage.base import StorageBase
from simvue.exception import ObjectNotFoundError


@click.group("storage")
@click.pass_context
def simvue_storage(_):
    """View and manage Simvue storages"""
    pass


@simvue_storage.group("add")
@click.pass_context
def simvue_storage_add(_) -> None:
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
        storage: StorageBase = simvue_cli.actions.get_storage(storage_id)
        storage_info = storage.to_dict()
        click.echo(json.dumps(dict(storage_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve storage '{storage_id}': {e.args[0]}"
        if not ctx.obj["plain"]:
            error_msg = click.style(error_msg, fg="red", bold=True)
        click.echo(error_msg)


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
            _ = simvue_cli.actions.get_storage(storage_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"storage '{storage_id}' not found"
            if ctx.obj["plain"]:
                click.echo(error_msg)
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
            click.echo(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue_storage.command("list")
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
    table_format: str,
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
        columns.append("is_tenant_useable")
    if default:
        columns.append("is_default")
    if enabled:
        columns.append("is_enabled")

    table = create_objects_display(
        columns,
        storages,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)
