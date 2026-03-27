"""Simvue Run Commands."""

import time
import click
import click_option_group
import tabulate
import pathlib
import sys
import json
import re
import plotext as plt

from click_option_group import optgroup
from typing import Literal, TYPE_CHECKING

from simvue_cli.cli.display import create_objects_display
from simvue_cli.validation import (
    MetricName,
    ObjectID,
    SimvueName,
    SimvueFolder,
    JSONType,
    TimeFormat,
    TimeInterval,
)
from simvue.exception import ObjectNotFoundError
from simvue.api.objects.filter import Status
import simvue_cli.actions
import simvue_cli.plot

from simvue.api.objects import Run

if TYPE_CHECKING:
    from simvue.api.objects.filter import RunsFilter


@click.group("run")
@click.pass_context
def simvue_run(_) -> None:
    """Create or retrieve Simvue runs"""
    pass


@simvue_run.command("create")
@click.pass_context
@click.option(
    "--create-only", help="Create run but do not start it", is_flag=True, default=False
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
    """Remove runs from the Simvue server"""
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
                click.echo(error_msg)
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
            click.echo(response_message)
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
            click.echo(error_msg)
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
            click.echo(error_msg)
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
    type=click.IntRange(min=1),
    help="Maximum number of runs to retrieve",
    default=20,
    show_default=True,
)
@click.option(
    "--sort-by",
    help="Specify columns to sort by",
    multiple=True,
    default=["created"],
    type=click.Choice(["created", "started", "endtime", "modified", "name"]),
    show_default=True,
)
@click.option("--reverse", help="Reverse ordering", default=False, is_flag=True)
@click.option("--shared", help="Include shared runs", default=False, is_flag=True)
@click.option("--starred", help="Filter to favorited runs", default=False, is_flag=True)
@click.option("-t", "--created", is_flag=True, help="Show the created time.")
@optgroup.group(
    name="Run attribute filters", help="Specify columns to display and/or filter on."
)
@optgroup.option(
    "-T",
    "--tags",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter tags, passing of TEXT is optional. Tags in filter must be comma separated.",
)
@optgroup.option(
    "-n",
    "--name",
    is_flag=False,
    flag_value="show-only",
    type=SimvueName,
    help="Show / filter names",
)
@optgroup.option(
    "-u", "--user", is_flag=True, flag_value="show-only", help="Show / filter users"
)
@optgroup.option(
    "--created-within", help='Filter by creation time, e.g. "10h".', type=TimeInterval
)
@optgroup.option(
    "--started-within", help='Filter by start time, e.g. "10h"', type=TimeInterval
)
@optgroup.option(
    "--ended-within", help='Filter by end time, e.g. "10h"', type=TimeInterval
)
@optgroup.option(
    "--modified-within", help="Filter by last modified time.", type=TimeInterval
)
@optgroup.option(
    "-d",
    "--description",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter description",
)
@optgroup.option(
    "-s",
    "--status",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter status, passing of TEXT is optional.",
    type=Status,
)
@optgroup.option(
    "-f",
    "--folder",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter folder, passing of TEXT is optional.",
    type=SimvueFolder,
    show_default=True,
)
@optgroup.option("-m", "--metadata", multiple=True, help="Show metadata value")
@optgroup.option(
    "--working-dir",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter working directory, passing of TEXT is optional.",
)
@optgroup.option(
    "--gpu-name",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter GPU name, passing of TEXT is optional.",
)
@optgroup.option(
    "--gpu-driver",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter GPU driver, passing of TEXT is optional.",
)
@optgroup.option(
    "--cpu-arch",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter CPU architecture, passing of TEXT is optional.",
)
@optgroup.option(
    "--cpu-processor",
    is_flag=False,
    flag_value="show-only",
    help="Show / filter CPU processoritecture, passing of TEXT is optional.",
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def list_runs(
    ctx,
    table_format: str,
    tags: Literal["show-only"] | str | None,
    description: Literal["show-only"] | str | None,
    user: Literal["show-only"] | str | None,
    created: bool,
    enumerate_: bool,
    name: Literal["show-only"] | str | None,
    folder: Literal["show-only"] | str | None,
    status: Literal["show-only"] | Status | None,
    gpu_name: Literal["show-only"] | str | None,
    gpu_driver: Literal["show-only"] | str | None,
    cpu_arch: Literal["show-only"] | str | None,
    cpu_processor: Literal["show-only"] | str | None,
    created_within: int | None,
    started_within: int | None,
    ended_within: int | None,
    modified_within: int | None,
    working_dir: Literal["show-only"] | str | None,
    args: str,
    shared: bool,
    starred: bool,
    **kwargs,
) -> None:
    """Retrieve runs list from Simvue server"""
    _metadata = [
        arg.replace("--", "") for arg in args if re.findall("^--metadata", arg)
    ]

    # To avoid ambiguity only allow shared to activated by command line argument
    if not shared:
        _filter: "RunsFilter" = Run.filter().owner()
    else:
        _filter = Run.filter().exclude_owner()

    if starred:
        _filter = _filter.starred()

    if _metadata:
        kwargs["metadata"] = True

    columns = ["id"] + _metadata

    if created:
        columns.append("created")

    if started_within:
        _filter = _filter.started_within(hours=started_within)

    if modified_within:
        _filter = _filter.modified_within(hours=modified_within)

    if created_within:
        _filter = _filter.created_within(hours=created_within)

    if ended_within:
        _filter = _filter.ended_within(hours=ended_within)

    if working_dir == "show-only":
        kwargs["system_info"] = True
        columns.append("system.cwd")
    elif working_dir:
        kwargs["system_info"] = True
        _filter = _filter.has_working_directory(working_dir)

    if gpu_name == "show-only":
        kwargs["system_info"] = True
        columns.append("system.gpu.name")
    elif gpu_name:
        kwargs["system_info"] = True
        _filter = _filter.has_gpu(name=gpu_name)

    if gpu_driver == "show-only":
        kwargs["system_info"] = True
        columns.append("system.gpu.driver")
    elif gpu_driver:
        kwargs["system_info"] = True
        _filter = _filter.has_gpu(driver=gpu_driver)

    if cpu_arch == "show-only":
        kwargs["system_info"] = True
        columns.append("system.cpu.arch")
    elif cpu_arch:
        kwargs["system_info"] = True
        _filter = _filter.has_cpu(architecture=cpu_arch)

    if cpu_processor == "show-only":
        kwargs["system_info"] = True
        columns.append("system.cpu.processor")
    elif cpu_processor:
        kwargs["system_info"] = True
        _filter = _filter.has_cpu(processor=cpu_processor)

    if name == "show-only":
        columns.append("name")
    elif name:
        _filter = _filter.has_name(name)

    if folder == "show-only":
        columns.append("folder")
    elif folder:
        _filter = _filter.in_folder(folder)

    if tags == "show-only":
        columns.append("tags")
    elif tags:
        _tags: list[str] = tags.split(",")
        for tag in _tags:
            if not (_tag := tag.strip().rstrip()):
                continue
            _filter = _filter.has_tag(_tag)

    if user == "show-only":
        columns.append("user")
    elif user:
        _filter = _filter.owner(user)

    if description == "show-only":
        columns.append("description")
    elif description:
        _filter = _filter.has_description_containing(description)

    if status == "show-only":
        columns.append("status")
    elif status:
        _filter = _filter.has_status(status)

    kwargs["filters"] = _filter.as_list()

    runs = simvue_cli.actions.get_runs_list(**kwargs)

    table = create_objects_display(
        columns,
        runs,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@simvue_run.command("json")
@click.pass_context
@click.argument("run_id", required=False)
def get_run_json(ctx, run_id: str) -> None:
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
        if not ctx.obj["plain"]:
            error_msg = click.style(error_msg, fg="red", bold=True)
        click.echo(error_msg)
        sys.exit(1)


@simvue_run.command("artifacts")
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
@click.option("--name", is_flag=True, flag_value=None, help="Show artifact name")
@click.option("--size", is_flag=True, help="Show artifact size")
@click.argument("run_id", required=False)
def get_run_artifacts(
    ctx,
    run_id: str,
    table_format: str,
    enumerate_: bool,
    original_path: bool,
    storage: bool,
    mime_type: bool,
    created: bool,
    user: bool,
    download_url: bool,
    uploaded: bool,
    name: str | None,
    size: bool,
    **_,
) -> None:
    """Retrieve the artifacts for a given Run from the Simvue server

    If no RUN_ID is provided the input is read from stdin
    """
    if not run_id:
        run_id = input()

    try:
        if not (artifacts := list(simvue_cli.actions.get_run_artifacts(run_id))):
            raise SystemExit
    except SystemExit:
        sys.exit(1)
    except (ObjectNotFoundError, RuntimeError) as e:
        _error_msg = f"Failed to retrieve run '{run_id}': {e.args[0]}"
        if not ctx.obj["plain"]:
            _error_msg = click.style(_error_msg, fg="red", bold=True)
        click.echo(_error_msg)
        sys.exit(1)

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
        artifacts,
        plain_text=ctx.obj["plain"],
        enumerate_=enumerate_,
        format=table_format,
    )
    click.echo(table)


@simvue_run.command("pull")
@click.pass_context
@click.option(
    "-o",
    "--output-dir",
    help="Output directory.",
    default=f"{pathlib.Path.cwd().joinpath('{run_id}')}",
    show_default=True,
)
@click.argument("run_id", required=False)
def pull_simvue_run(ctx, output_dir: str, run_id: str) -> None:
    """Retrieve artifacts for the given Simvue run.

    Downloads the artifacts to the specified directory."""
    if not run_id:
        run_id = input()

    try:
        _downloaded_files: list[pathlib.Path] = simvue_cli.actions.pull_run(
            run_id=run_id,
            output_dir=pathlib.Path(output_dir.format(run_id=run_id)),
            plain=ctx.obj["plain"],
        )
        if not _downloaded_files:
            click.echo("No artifacts found.")
            return
        _disp_str = "\n".join(f"{file}" for file in _downloaded_files)
        click.echo(_disp_str if ctx.obj["plain"] else click.style(_disp_str, bold=True))
    except RuntimeError as e:
        _disp_str = f"Failed to download run '{run_id}': {e.args[0]}"
        click.echo(
            _disp_str
            if ctx.obj["plain"]
            else click.style(_disp_str, fg="red", bold=True)
        )
        sys.exit(1)


@simvue_run.command("plot")
@click.pass_context
@click.argument("run_id", type=ObjectID, nargs=-1)
@click.option("--metric", type=MetricName, multiple=True, required=True)
@click.option(
    "--time-format", type=TimeFormat, required=False, default="step", show_default=True
)
@optgroup.group(name="Plotting Options", help="Customise the plotting output")
@optgroup.option(
    "-Y",
    "--threshold",
    type=float,
    help="Superimpose threshold line at point on metric axis.",
    default=None,
)
@optgroup.option(
    "-X",
    "--cutoff",
    type=float,
    help="Superimpose threshold line at point on time axis.",
    default=None,
)
@optgroup.option(
    "--watch", is_flag=True, default=False, help="Monitor the metric data live."
)
def plot_run_metric(
    _,
    run_id: list[str],
    metric: list[str],
    watch: bool,
    threshold: float | None,
    time_format: Literal["step", "time", "timestamp"],
    cutoff: float | None,
) -> None:
    """Plot a metric from a given run."""

    def _get_plot() -> str:
        _plot_iter = simvue_cli.actions.get_metrics(
            run_ids=run_id, metric_names=metric, x_axis=time_format
        )
        return simvue_cli.plot.plot_simvue_metrics(
            plot_iterator=_plot_iter,
            time_label=time_format,
            marker_y_coord=threshold,
            marker_x_coord=cutoff,
        )

    try:
        while True:
            if not watch:
                sys.exit(0)
            _ = _get_plot()
            time.sleep(2)
            plt.cld()
    except KeyboardInterrupt:
        sys.exit(0)
