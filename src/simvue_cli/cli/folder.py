"""Simvue Folder Commands."""

import click
import re
import json
import tabulate
import sys

from .display import create_objects_display, format_folder_tree

import simvue_cli.actions

from simvue.api.objects import Folder
from simvue.exception import ObjectNotFoundError
from simvue.models import FOLDER_REGEX


@click.group("folder")
@click.pass_context
def simvue_folder(_) -> None:
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
def get_folder_json(folder_id: str | None) -> None:
    """Retrieve folder information from Simvue server

    If no folder_ID is provided the input is read from stdin.
    Input can be folder unique identifier or name.
    """
    if not folder_id:
        folder_id = input()

    if re.match(FOLDER_REGEX, folder_id):
        try:
            folder: Folder = simvue_cli.actions.get_folder_by_path(folder_id)
        except StopIteration:
            error_msg: str = f"Failed to retrieve folder '{folder_id}': No such folder."
            click.secho(error_msg, fg="red", bold=True)
            return
    else:
        try:
            folder = simvue_cli.actions.get_folder(folder_id)
        except ObjectNotFoundError as e:
            error_msg = f"Failed to retrieve folder '{folder_id}': {e.args[0]}"
            click.secho(error_msg, fg="red", bold=True)
            return
    click.echo(folder.path)
    folder_info = folder.to_dict()
    click.echo(json.dumps(dict(folder_info.items()), indent=2))


@simvue_folder.command("remove")
@click.pass_context
@click.argument("folder_ids", type=str, nargs=-1, required=False)
@click.option(
    "-i",
    "--interactive",
    help="Prompt for confirmation on removal",
    type=bool,
    default=False,
    is_flag=True,
)
@click.option(
    "-r", "--recurse", help="Recursively remove folders.", default=False, is_flag=True
)
@click.option(
    "-f",
    "--force",
    help="Forcefully delete folder even if it contains runs.",
    is_flag=True,
    default=False,
)
@click.option(
    "-c",
    "--content",
    help="Delete only folder content not folder itself.",
    is_flag=True,
    default=False,
)
def delete_folder(
    ctx,
    folder_ids: list[str] | None,
    interactive: bool,
    force: bool,
    recurse: bool,
    content: bool,
) -> None:
    """Remove a Folder from the Simvue server"""
    if not folder_ids:
        folder_ids = []
        for line in sys.stdin:
            if not line.strip():
                continue
            folder_ids += [k.strip() for k in line.split(" ")]

    force = force if not content else False

    for folder_id in folder_ids:
        try:
            _folder = simvue_cli.actions.get_folder(folder_id)
        except (ObjectNotFoundError, RuntimeError):
            error_msg = f"Folder '{folder_id}' not found"
            if ctx.obj["plain"]:
                print(error_msg)
            else:
                click.secho(error_msg, fg="red", bold=True)
            sys.exit(1)

        if _folder.path == "/":
            _warn_message: str = "Root directory cannot be deleted."
            if ctx.obj["plain"]:
                print(_warn_message)
            else:
                click.secho(_warn_message, fg="red", bold=True)
            sys.exit(1)

        if interactive:
            remove = click.confirm(
                f"Remove folder '{folder_id}'" + " and contained runs"
                if force
                else "" + "?"
            )
            if not remove:
                continue

        try:
            simvue_cli.actions.delete_folder(
                folder_id, force=force, recurse=recurse, contents_only=content
            )
        except ValueError as e:
            click.echo(
                e.args[0]
                if ctx.obj["plain"]
                else click.style(e.args[0], fg="red", bold=True)
            )
            sys.exit(1)
        except RuntimeError as e:
            if "Folder is in use" in e.args[0]:
                _out_msg = f"Failed to delete folder '{folder_id}', folder in use."
            else:
                _out_msg = e.args[0]
            click.echo(
                _out_msg
                if ctx.obj["plain"]
                else click.style(_out_msg, fg="red", bold=True)
            )
            sys.exit(1)

        response_message = f"Folder '{folder_id}' removed successfully."

        if ctx.obj["plain"]:
            print(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue_folder.command("tree")
@click.argument("folder_id", required=False)
@click.option(
    "-l", "--detail", help="Include folder details", default=False, is_flag=True
)
def display_folder_tree(folder_id: str | None, detail: bool) -> None:
    """Display tree graph of folder structure.

    if no folder_ID is provided the input is read from stdin
    """
    if not folder_id:
        folder_id = input()

    if re.match(FOLDER_REGEX, folder_id):
        try:
            folder: Folder = simvue_cli.actions.get_folder_by_path(folder_id)
        except StopIteration:
            error_msg: str = f"Failed to retrieve folder '{folder_id}': No such folder."
            click.secho(error_msg, fg="red", bold=True)
            return
    else:
        try:
            folder = simvue_cli.actions.get_folder(folder_id)
        except ObjectNotFoundError as e:
            error_msg = f"Failed to retrieve folder '{folder_id}': {e.args[0]}"
            click.secho(error_msg, fg="red", bold=True)
            return
    if detail:
        _details: dict[str, dict] = simvue_cli.actions.get_folder_details(folder)
        print(_details)
    click.echo(format_folder_tree(folder.tree))
