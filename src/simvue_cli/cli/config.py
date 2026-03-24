"""Simvue CLI Configuration commands."""

import click
import pathlib
import sys
import toml
import os


import simvue_cli.config

from click_params import PUBLIC_URL


@click.group("config")
@click.option(
    "_global",
    "--global/--all",
    default=None,
    help="Update global or all configurations. Default of None will update local configuration only.",
    show_default=True,
)
@click.pass_context
def config(ctx, _global: bool | None) -> None:
    """Configure Simvue"""
    if _global is not None:
        ctx.obj["config_locations"] = "global" if _global else "all"
    else:
        ctx.obj["config_locations"] = "project"


@config.command("server.url")
@click.argument("url", type=PUBLIC_URL)
@click.pass_context
def config_set_url(ctx, url: str) -> None:
    """Update Simvue configuration URL"""
    _profile_name, _ = ctx.obj["profile"]
    _target_locations = ctx.obj["config_locations"]
    _out_files: list[pathlib.Path] = simvue_cli.config.set_profile_option(
        profile_name=_profile_name, key="url", value=url, targets=_target_locations
    )
    for out_file in _out_files:
        click.secho(f"Wrote URL value to '{out_file}'")
    if not _out_files:
        sys.exit(1)


@config.command("server.token")
@click.argument("token", type=str)
@click.pass_context
def config_set_token(ctx, token: str) -> None:
    """Update Simvue configuration Token"""
    _profile_name, _ = ctx.obj["profile"]
    _target_locations = ctx.obj["config_locations"]
    _out_files: list[pathlib.Path] = simvue_cli.config.set_profile_option(
        profile_name=_profile_name, key="token", value=token, targets=_target_locations
    )
    for out_file in _out_files:
        click.secho(f"Wrote token value to '{out_file}'")


@config.command("show")
@click.pass_context
def config_show(ctx) -> None:
    """Show the current Simvue configuration."""

    # Remove environment override to show full listing
    # instead highlight current server
    _env_url = os.environ.get("SIMVUE_URL")
    _env_token = os.environ.get("SIMVUE_TOKEN")

    _config_file, _config = simvue_cli.config.get_current_configuration()
    _current_url: str | None = None
    _current_token: str | None = None

    click.echo(f"Using configuration from '{_config_file}'.\n")

    _name, _profile = ctx.obj["profile"]

    if _profile:
        _current_url = _profile.url
        _current_token = _profile.token
        _config_str = toml.dumps(_config)

        if ctx.obj["plain"] and _name:
            _config_str = _config_str.replace(
                f"[profiles.{_name}]", f"[profiles.{_name}]  <<< ACTIVE PROFILE"
            )
        elif _name:
            _config_str = _config_str.replace(
                f"[profiles.{_name}]",
                click.style(f"[profiles.{_name}]", bold=True, fg="cyan"),
            )

        click.secho(_config_str)
        return

    if _config_file:
        click.secho(f"Using configuration from '{_config_file}'.\n")
    if _env_url and _env_token:
        click.secho("Using environment variables:")
        click.secho(f" SIMVUE_URL={_env_url}")
        click.secho(" SIMVUE_TOKEN=****\n")
        _current_url = _env_url
        _current_token = _env_token
    elif not _config_file:
        click.secho("No config file found.\n", fg="red", bold=True)
    click.secho(toml.dumps(_config))

    if not _config_file and (not _current_url or not _current_token):
        raise sys.exit(1)
