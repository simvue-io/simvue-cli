"""Simvue process monitor Commands."""

import click
import sys
import click_option_group

import simvue_cli.actions

from simvue_cli.validation import SimvueFolder, SimvueName

from simvue.api.objects import Run


@click.command("monitor")
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
