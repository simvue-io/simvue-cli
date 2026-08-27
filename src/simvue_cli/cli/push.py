"""Commands for Pushing Data to a Server."""

import click
import pathlib

import simvue_cli.actions

from simvue_cli.validation import JSONType


@click.group("push")
@click.pass_context
def push(_) -> None:
    """Push local data to the Simvue server."""


@push.command("runs")
@click.pass_context
@click.argument(
    "input_file",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        allow_dash=False,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
)
@click.option("--name", default=None, help="Name to set to all runs.")
@click.option("--folder", default=None, help="Simvue folder to add runs to.")
@click.option(
    "--tenant",
    "tenant_visible",
    is_flag=True,
    default=False,
    help="Share with tenant.",
)
@click.option(
    "--public",
    "public_visible",
    is_flag=True,
    default=False,
    help="Share with public.",
)
@click.option(
    "--user", "user_list", multiple=True, help="Share with user.", default=None
)
@click.option(
    "--metadata",
    "global_metadata",
    type=JSONType,
    help="Metadata to append to all runs in the form of a JSON string.",
)
@click.option(
    "--from-metadata",
    is_flag=True,
    help="Create runs from a list of metadata only.",
)
def push_runs(
    ctx,
    input_file: pathlib.Path,
    from_metadata: bool,
    tenant_visible: bool,
    public_visible: bool,
    user_list: list[str],
    **kwargs,
) -> None:
    """Push sets of runs to the Simvue server.

    The default is to create runs from a JSON definition containing a list of run specifications.

    If the option `--from-metadata` runs are created from metadata only having no metrics information.
    These runs are taken either from JSON or CSV as sets of metadata.

    Only one visibility option from `--tenant`, `--public` or `--user`, may be specified.
    """
    _plain_text = ctx.obj["plain"]

    if sum([int(i or 0) for i in (user_list, public_visible, tenant_visible)]) > 1:
        raise click.UsageError("Cannot specify above one visibility option.")

    if from_metadata:
        if input_file.suffix == ".csv":
            _folder_id = simvue_cli.actions.push_delim_metadata(
                input_file,
                delimiter=",",
                **kwargs,
                public_visible=public_visible,
                tenant_visible=tenant_visible,
                user_list=user_list,
            )
        elif input_file.suffix == ".json":
            _folder_id = simvue_cli.actions.push_json_metadata(
                input_file,
                public_visible=public_visible,
                tenant_visible=tenant_visible,
                user_list=user_list,
                **kwargs,
            )
        else:
            _out_msg: str = f"Unsupported file type '{input_file.suffix}'"
            if not _plain_text:
                _out_msg = click.style(_out_msg, fg="red", bold=True)
            click.echo(_out_msg)
            raise click.Abort
        click.echo(_folder_id)
        return
    if input_file.suffix == ".json":
        _folder_ids = simvue_cli.actions.push_json_runs(
            input_file,
            public_visible=public_visible,
            tenant_visible=tenant_visible,
            user_list=user_list,
            **kwargs,
        )
    else:
        _out_msg: str = f"Unsupported file type '{input_file.suffix}'"
        if not _plain_text:
            _out_msg = click.style(_out_msg, fg="red", bold=True)
        click.echo(_out_msg)
        raise click.Abort
    click.echo("\n".join(_folder_ids))
