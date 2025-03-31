"""
Simvue Configuration
====================

Functionality for updating configuration of Simvue API via the CLI
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import pathlib
import toml

from simvue.config.user import SimvueConfiguration

SIMVUE_CONFIG_FILENAME: str = "simvue.toml"
SIMVUE_CONFIG_INI_FILENAME: str = "simvue.ini"


def set_configuration_option(
    section: str, key: str, value: str | int | float, local: bool
) -> pathlib.Path:
    """Set a configuation value for Simvue

    Parameters
    ----------
    section : str
        section of configuration file to modify
    key : str
        key within the given section to modify
    value : str | int | float
        new value for this section-key combination
    local : bool
        whether to modify the global or local Simvue configuration

    Returns
    -------
    pathlib.Path
        path to the modified configuration file
    """
    file_name: pathlib.Path

    if local:
        file_name = pathlib.Path().cwd().joinpath(SIMVUE_CONFIG_FILENAME)
    else:
        file_name = pathlib.Path().home().joinpath(f".{SIMVUE_CONFIG_FILENAME}")

    config = toml.load(file_name) if file_name.exists() else {}

    if not config.get(section):
        config[section] = {}

    config[section][key] = value

    toml.dump(config, file_name.open("w", encoding="utf-8"))

    return file_name


def get_url_and_headers() -> tuple[str, dict[str, str]]:
    """Retrieve the Simvue server URL and headers for requests"""
    _config = SimvueConfiguration.fetch()
    _headers: dict[str, str] = {
        "Authorization": f"Bearer {_config.server.token.get_secret_value()}"
    }
    return _config.server.url, _headers
