"""Miscellaneous click.commands."""

import click
import contextlib
import simvue.client as simvue_client
import simvue_cli.server
import requests
import time
import datetime
import simvue_cli.actions
import shutil
import importlib
import tabulate

from simvue_cli.cli.display import SIMVUE_LOGO


@click.command("ping")
@click.option(
    "-t",
    "--timeout",
    help="Timeout the command after n seconds",
    default=None,
    type=int,
)
def ping_server(timeout: int | None) -> None:
    """Ping the Simvue server"""
    successful_pings: int = 0
    with contextlib.suppress(KeyboardInterrupt):
        url = simvue_client.Client()._user_config.server.url
        ip_address = simvue_cli.server.get_ip_of_url(url)
        counter: int = 0
        while True:
            if timeout and counter > timeout:
                return
            start_time = time.time()
            try:
                server_version: int | str = simvue_cli.actions.get_server_version()
                if (
                    status_code := 200
                    if isinstance(server_version, str)
                    else server_version
                ) != 200:
                    raise RuntimeError
                successful_pings += 1
                end_time = time.time()  # Record the end time
                elapsed_time = (end_time - start_time) * 1000  # Convert to milliseconds
                click.secho(
                    f"Reply from {url} ({ip_address}): status_code={status_code}, time={elapsed_time:.2f}ms"
                )
            except (requests.ConnectionError, requests.Timeout, RuntimeError):
                click.secho(
                    f"Reply from {url} ({ip_address}): status_code={status_code}, error"
                )

            time.sleep(1)
            counter += 1


@click.command("whoami")
@click.option("-u", "--user", help="click.echo only the user name", default=False)
@click.option("-t", "--tenant", help="click.echo only the tenant", default=False)
def whoami(user: bool, tenant: bool) -> None:
    """Retrieve current user information"""
    if user and tenant:
        click.secho("cannot click.echo 'only' with more than one choice")
        raise click.Abort
    user_info = simvue_cli.actions.user_info()
    user_name = user_info.get("user")
    tenant_info = user_info.get("tenant")
    if user:
        click.secho(user_name)
    elif tenant:
        click.secho(tenant_info)
    else:
        click.secho(f"{user_name}({tenant_info})")


@click.command("about")
@click.pass_context
def about_simvue(ctx) -> None:
    """Display full information on Simvue instance"""
    width = shutil.get_terminal_size().columns
    if not ctx.obj.get("plain"):
        click.echo(
            "\n".join(
                "\t" * int(0.015 * width) + f"{r}" for r in SIMVUE_LOGO.split("\n")
            )
        )
        click.echo(f"\n{width * '='}\n")
        click.echo(
            "\n" + "\t" * int(0.04 * width) + "Provided under the Apache-2.0 License"
        )
        click.echo(
            "\t" * int(0.04 * width)
            + f"© Copyright {datetime.datetime.now().strftime('%Y')} Simvue Development Team\n"
        )
    out_table: list[list[str]] = []
    with contextlib.suppress(importlib.metadata.PackageNotFoundError):
        out_table.append(
            ["CLI Version: ", importlib.metadata.version(simvue_cli.__name__)]
        )
    with contextlib.suppress(importlib.metadata.PackageNotFoundError):
        out_table.append(
            ["Python API Version: ", importlib.metadata.version(simvue_client.__name__)]
        )
    # with contextlib.suppress(Exception):
    server_version: int | str = simvue_cli.actions.get_server_version()
    if isinstance(server_version, int):
        raise RuntimeError
    out_table.append(["Server Version: ", server_version])
    if not ctx.obj.get("plain"):
        click.echo(
            "\n".join(
                "\t" * int(0.045 * width) + f"{r}"
                for r in tabulate.tabulate(out_table, tablefmt="plain")
                .__str__()
                .split("\n")
            )
        )
        click.echo(f"\n{width * '='}\n")
    else:
        click.echo(tabulate.tabulate(out_table, tablefmt="plain").__str__())


@click.command("purge")
@click.pass_context
def purge_simvue(_) -> None:
    """Remove all local Simvue files in user home area."""

    click.echo(
        "Simvue user files deleted successfully."
        if simvue_cli.actions.purge_local_simvue_files()
        else "Nothing to do."
    )
