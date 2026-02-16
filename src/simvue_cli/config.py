"""
Simvue Configuration
====================

Functionality for updating configuration of Simvue API via the CLI
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import pathlib
import toml
import urllib.parse

from simvue.config.user import ServerSpecifications, SimvueConfiguration

SIMVUE_CONFIG_FILENAME: str = "simvue.toml"
SIMVUE_CONFIG_INI_FILENAME: str = "simvue.ini"


def get_current_configuration() -> tuple[pathlib.Path, dict[str, str]]:
    """Return the current Simvue configuration."""
    _config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    return _config.config_file(), _config.model_dump(warnings="none", mode="json")


def set_configuration_option(
    section: str,
    key: str,
    value: str | int | float,
    local: bool,
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
    _config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    _headers: dict[str, str] = {
        "Authorization": f"Bearer {_config.server.token.get_secret_value()}"
    }
    return _config.server.url, _headers


def get_profile(profile_name: str | None) -> tuple[str | None, ServerSpecifications]:
    """Retrieve profile by name or hostname.

    Allows for retrieval of a profile by either name or hostname.
    If 'None' return the default.

    Parameters
    ----------
    profile_name : str | None
        specify the server profile name, else default.

    Returns
    -------
    tuple[str | None, ServerSpecifications]
        name of profile
        server profile information.
    """
    _config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    try:
        _default_profile: str = urllib.parse.urlparse(_config.server.url).hostname
    except AttributeError as e:
        raise RuntimeError(f"Could not parse default URL '{_config.server.url}'")
    if not profile_name or profile_name == _default_profile:
        return None, _config.server
    for name, profile in _config.profiles.items():
        if profile_name == name:
            return name, profile
        try:
            _hostname: str = urllib.parse.urlparse(profile.url).hostname
        except AttributeError as e:
            raise RuntimeError(f"Could not parse default URL '{profile.url}'")
        if profile_name == _hostname:
            return name, profile
    raise ValueError(f"No such profile '{profile_name}'.")
