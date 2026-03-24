"""Simvue Tag Commands."""

import click
import tabulate
import json
import sys

import simvue_cli.actions

from simvue_cli.cli.display import create_objects_display
from simvue_cli.validation import SimvueName
from simvue.api.objects import Tag
from simvue.exception import ObjectNotFoundError


@click.group("tag")
@click.pass_context
def simvue_tag(_) -> None:
    """Create or retrieve Simvue tags"""
    pass


@simvue_tag.command("create")
@click.pass_context
@click.argument("name", type=SimvueName)
@click.option(
    "--color",
    type=str,
    default=None,
    help="Color for this tag, e.g. '#fffff', 'blue', 'rgb(23, 54, 34)'",
)
@click.option("--description", type=str, default=None, help="Description for this tag.")
def create_tag(ctx, **kwargs) -> None:
    """Create a tag"""
    result = simvue_cli.actions.create_simvue_tag(**kwargs)
    alert_id = result.id
    click.echo(alert_id if ctx.obj["plain"] else click.style(alert_id))


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
@click.option("--description", is_flag=True, help="Show descriptions")
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
    enumerate_: bool,
    created: bool,
    table_format: str | None,
    name: bool,
    description: bool,
    color: bool,
    **kwargs,
) -> None:
    """Retrieve tags list from Simvue server."""
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

    if description:
        columns.append("description")

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
@click.pass_context
def get_tag_json(ctx, tag_id: str) -> None:
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
        if not ctx.obj["plain"]:
            error_msg = click.style(error_msg, fg="red", bold=True)
        click.echo(error_msg)


@simvue_tag.command("remove")
@click.pass_context
@click.argument("tag_ids", type=str, nargs=-1, required=False)
@click.option(
    "-i",
    "--interactive",
    help="Prompt for confirmation on removal",
    type=bool,
    default=False,
    is_flag=True,
)
def delete_tag(ctx, tag_ids: list[str] | None, interactive: bool) -> None:
    """Remove a tag from the Simvue server"""
    if not tag_ids:
        tag_ids = []
        for line in sys.stdin:
            if not line.strip():
                continue
            tag_ids += [k.strip() for k in line.split(" ")]

    for tag_id in tag_ids:
        try:
            _ = simvue_cli.actions.get_tag(tag_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"Tag '{tag_id}' not found"
            if ctx.obj["plain"]:
                click.echo(error_msg)
            else:
                click.secho(error_msg, fg="red", bold=True)
            sys.exit(1)

        if interactive:
            remove = click.confirm(f"Remove tag '{tag_id}'?")
            if not remove:
                continue

        try:
            simvue_cli.actions.delete_tag(tag_id)
        except ValueError as e:
            click.echo(
                e.args[0]
                if ctx.obj["plain"]
                else click.style(e.args[0], fg="red", bold=True)
            )
            sys.exit(1)

        response_message = f"Tag '{tag_id}' removed successfully."

        if ctx.obj["plain"]:
            click.echo(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")
