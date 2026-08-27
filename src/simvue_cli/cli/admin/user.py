"""Simvue User Commands."""

import click
import tabulate
import json
import sys

import simvue_cli.actions
from simvue_cli.cli.display import create_objects_display
from simvue_cli.validation import Email, FullName, UserName
from simvue.api.objects import User
from simvue.exception import ObjectNotFoundError


@click.group("user")
@click.pass_context
def simvue_user(_) -> None:
    """Manage server users"""
    pass


@simvue_user.command("list")
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
        columns.append("is_admin")
    if manager:
        columns.append("is_manager")
    if enabled:
        columns.append("is_enabled")
    if read_only:
        columns.append("is_readonly")
    if deleted:
        columns.append("is_deleted")

    table = create_objects_display(
        columns,
        users,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@simvue_user.command("json")
@click.argument("user_id", required=False)
@click.pass_context
def get_user_json(ctx, user_id: str) -> None:
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
        if not ctx.obj["plain"]:
            error_msg = click.style(error_msg, fg="red", bold=True)
        click.echo(error_msg)


@simvue_user.command("add")
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
    """Create a new Simvue user under the given tenant."""
    user: User = simvue_cli.actions.create_simvue_user(**kwargs)
    click.echo(user.id if ctx.obj["plain"] else click.style(user.id))


@simvue_user.command("remove")
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
                click.echo(error_msg)
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
            click.echo(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")
