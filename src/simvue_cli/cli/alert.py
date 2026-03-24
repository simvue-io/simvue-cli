"""Simvue Alert Commands."""

import click
import json
import tabulate
import sys
import simvue_cli.actions

from simvue.api.objects.alert.base import AlertBase
from simvue.exception import ObjectNotFoundError

from simvue_cli.validation import SimvueName
from .display import create_objects_display


@click.group("alert")
@click.pass_context
def simvue_alert(_) -> None:
    """Create and list Simvue alerts"""
    pass


@simvue_alert.command("trigger")
@click.pass_context
@click.argument("run_id")
@click.argument("alert_id")
@click.option(
    "--ok",
    "is_ok",
    is_flag=True,
    help="Set alert to status 'ok' as opposed to critical.",
    show_default=True,
)
def trigger_alert(ctx, is_ok: bool, **kwargs) -> None:
    """Trigger a user alert"""
    try:
        simvue_cli.actions.trigger_user_alert(
            status="ok" if is_ok else "critical", **kwargs
        )
    except ValueError as e:
        if ctx.obj["plain"]:
            click.echo(e.args[0])
        else:
            click.secho(e.args[0], fg="red", bold=True)
        sys.exit(1)


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
                click.echo(error_msg)
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
            click.echo(response_message)
        else:
            click.secho(response_message, bold=True, fg="green")


@simvue_alert.command("json")
@click.argument("alert_id", required=False)
@click.pass_context
def get_alert_json(ctx, alert_id: str) -> None:
    """Retrieve alert information from Simvue server

    If no alert ID is provided the input is read from stdin
    """
    if not alert_id:
        alert_id = input()

    try:
        alert: AlertBase = simvue_cli.actions.get_alert(alert_id)
        alert_info = alert.to_dict()
        click.echo(json.dumps(dict(alert_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve alert '{alert_id}': {e.args[0]}"
        if not ctx.obj["plain"]:
            error_msg = click.style(error_msg, fg="red", bold=True)
        click.echo(error_msg)
