"""
Simvue CLI
==========

Command line tool for interfacing with a Simvue server, this interface allows
the user to submit metrics and retrieve information from the command line.
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import os
import sys
import click
import logging


import simvue_cli.config

from .config import config as config_cli
from .run import simvue_run as run_cli
from .alert import simvue_alert as alert_cli
from .folder import simvue_folder as folder_cli
from .utilities import ping_server, about_simvue, purge_simvue, whoami
from .admin import admin as admin_cli
from .tag import simvue_tag as tag_cli
from .storage import simvue_storage as storage_cli
from .artifact import simvue_artifact as artifact_cli
from .push import push as push_cli
from .monitor import monitor as monitor_cli
from .venv import venv_setup as venv_cli


logging.basicConfig()
logging.getLogger("simvue").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


@click.group("simvue-cli")
@click.version_option()
@click.option(
    "--plain", help="Run without color/formatting", default=False, is_flag=True
)
@click.option(
    "--profile", help="Specify alternative profile for commands.", default=None
)
@click.option(
    "-v", "--verbose", help="Increase verbosity.", default=False, is_flag=True
)
@click.pass_context
def simvue(ctx, plain: bool, profile: str | None, verbose: bool) -> None:
    """Simvue CLI for interacting with a Simvue server instance

    Provides functionality for the retrieval, creation and modification of server objects
    """
    if verbose:
        logging.getLogger(__name__).setLevel(logging.INFO)

    _formatting: dict[str, str | bool] = (
        {"bold": True, "fg": "red"} if not plain else {}
    )

    ctx.ensure_object(dict)
    ctx.obj["plain"] = plain
    ctx.obj["profile"] = (None, None)

    # A lot of commands should not use profile
    # and so should not be affected by this
    if not profile:
        return

    try:
        _name, _profile = simvue_cli.config.get_profile(profile)
    except (ValueError, RuntimeError) as e:
        click.echo(click.style(f"{e}", **_formatting))
        raise sys.exit(1)
    except FileNotFoundError:
        # No config files found so nothing to be done
        return

    ctx.obj["profile"] = (_name, _profile)

    if not _profile.url or not _profile.token:
        click.echo(
            click.style(
                f"Failed to retrieve URL and token for server '{profile or 'default'}'",
                **_formatting,
            )
        )
        raise sys.exit(1)

    logger.info(f"Referencing API server '{_profile.url}'")

    os.environ["SIMVUE_URL"] = f"{_profile.url}"
    os.environ["SIMVUE_TOKEN"] = _profile.token.get_secret_value()


simvue.add_command(config_cli)
simvue.add_command(run_cli)
simvue.add_command(alert_cli)
simvue.add_command(folder_cli)
simvue.add_command(ping_server)
simvue.add_command(whoami)
simvue.add_command(purge_simvue)
simvue.add_command(about_simvue)
simvue.add_command(admin_cli)
simvue.add_command(tag_cli)
simvue.add_command(storage_cli)
simvue.add_command(artifact_cli)
simvue.add_command(push_cli)
simvue.add_command(monitor_cli)
simvue.add_command(venv_cli)


if __name__ in "__main__":
    simvue()
