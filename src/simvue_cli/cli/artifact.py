"""Simvue Artifact Commands."""

import click
import json
from simvue.api.objects import Artifact
from simvue.exception import ObjectNotFoundError
import tabulate
import simvue_cli.actions
from simvue_cli.cli.display import create_objects_display


@click.group("artifact")
@click.pass_context
def simvue_artifact(_):
    """View and manage Simvue artifacts"""
    pass


@simvue_artifact.command("json")
@click.argument("artifact_id", required=False)
@click.pass_context
def get_artifact_json(ctx, artifact_id: str) -> None:
    """Retrieve artifact information from Simvue server

    If no ARTIFACT_ID is provided the input is read from stdin
    """
    if not artifact_id:
        artifact_id = input()

    try:
        artifact: Artifact = simvue_cli.actions.get_artifact(artifact_id)
        artifact_info = artifact.to_dict()
        click.echo(json.dumps(dict(artifact_info.items()), indent=2))
    except ObjectNotFoundError as e:
        error_msg = f"Failed to retrieve artifact '{artifact_id}': {e.args[0]}"
        if not ctx.obj["plain"]:
            error_msg = click.style(error_msg, fg="red", bold=True)
        click.echo(error_msg)


@simvue_artifact.command("list")
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
def artifact_list(
    ctx,
    table_format: str | None,
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
    artifacts = simvue_cli.actions.get_artifacts_list(**kwargs)
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
        columns.append("storage_id")
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
        artifacts,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)
