"""
Simvue Configuration
====================

Functionality for updating configuration of Simvue API via the CLI
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import pathlib
from typing import Literal
from simvue.utilities import find_first_instance_of_file
import toml
import urllib.parse

from simvue.config.user import (
    CONFIG_FILE_NAMES,
    ServerSpecifications,
    SimvueConfiguration,
)

SIMVUE_CONFIG_FILENAME: str = "simvue.toml"
SIMVUE_CONFIG_INI_FILENAME: str = "simvue.ini"


def get_current_configuration() -> tuple[pathlib.Path | None, dict[str, str]]:
    """Return the current Simvue configuration."""
    _config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    try:
        _config_file = _config.config_file()
    except FileNotFoundError:
        _config_file = None
    return _config_file, _config.model_dump(warnings="none", mode="json")


def set_configuration_option(
    section: str,
    key: str,
    value: str | int | float,
    targets: Literal["all", "project", "global"],
) -> list[pathlib.Path]:
    """Set a configuation value for Simvue

    Parameters
    ----------
    section : str
        section of configuration file to modify
    key : str
        key within the given section to modify
    value : str | int | float
        new value for this section-key combination
    targets : Literal['all', 'project', 'global']
        whether to apply this change to the project config,
        the user config or both

    Returns
    -------
    list[pathlib.Path]
        list of paths to the modified configuration files
    """

    _first_config_file = find_first_instance_of_file(SIMVUE_CONFIG_FILENAME)
    _global_config_file = pathlib.Path().home().joinpath(f".{SIMVUE_CONFIG_FILENAME}")

    _config_files: list[pathlib.Path] = []

    if targets in ("all", "project") and _first_config_file:
        _config_files.append(_first_config_file)
    if targets in ("all", "global") and _global_config_file.exists():
        _config_files.append(_global_config_file)
    if not _config_files:
        raise FileNotFoundError("No configuration files found.")

    for _config_file in _config_files:
        config = toml.load(_config_file) if _config_file.exists() else {}

        if not config.get(section):
            config[section] = {}

        config[section][key] = value

        _ = toml.dump(config, _config_file.open("w", encoding="utf-8"))

    return _config_files


def set_profile_option(
    profile_name: str | None,
    key: str,
    value: str,
    targets: Literal["all", "global", "project"],
) -> list[pathlib.Path]:
    """Modify profile setting."""
    # If no configs are found at all raise exception
    if not find_first_instance_of_file(CONFIG_FILE_NAMES):
        raise FileNotFoundError("No Simvue configuration files found on system.")

    # Look only for local config file
    _config_file = find_first_instance_of_file(CONFIG_FILE_NAMES[0])

    # If user explicitly requested to modify a project config but none found
    # throw an exception
    if targets == "project" and not _config_file:
        raise FileNotFoundError(
            "No project level Simvue configuration file found on system."
        )

    _global_config_file: pathlib.Path = pathlib.Path.home().joinpath(
        f".{SIMVUE_CONFIG_FILENAME}"
    )

    # If user explicitly requested to modify a global config but none found
    # throw an exception
    if targets == "global" and not _global_config_file.exists():
        raise FileNotFoundError(
            "No user level Simvue configuration file found on system."
        )

    # Read in contents of local and global configurations
    if not _global_config_file.exists():
        _global_config = {}
    else:
        _global_config = toml.load(_global_config_file)

    if not _config_file:
        _config = {}
    else:
        _config = toml.load(_config_file)

    if not profile_name:
        return set_configuration_option("server", key=key, value=value, targets=targets)

    # Based on the user settings append profiles to the search
    _search_profiles: dict[str, dict] = {}
    _config_profiles = _config.get("profiles", {})
    _global_config_profiles = _global_config.get("profiles", {})

    if targets in ("project", "all"):
        _search_profiles |= _config_profiles
    if targets in ("global", "all"):
        _search_profiles |= _global_config_profiles

    # Iterate through all profiles checking based on hostname
    # or name, returning the result when found
    for name, profile in _search_profiles.items():
        try:
            _hostname: str = urllib.parse.urlparse(profile["url"]).hostname
        except AttributeError:
            raise RuntimeError(f"Could not parse default URL '{profile['url']}'")
        if profile_name == name or profile_name == _hostname:
            _config_files: list[pathlib.Path] = []
            if name in _config_profiles and _config_file:
                _config_profiles[name][key] = value
                with _config_file.open("w") as out_f:
                    toml.dump(_config, out_f)
                _config_files.append(_config_file)
            if name in _global_config_profiles and _global_config_file:
                _global_config_profiles[name][key] = value
                with _global_config_file.open("w") as out_f:
                    toml.dump(_global_config, out_f)
                _config_files.append(_global_config_file)
            if _config_files:
                return _config_files
    raise ValueError(f"Could not find profile '{profile_name}'")


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
    If 'None' return the default. Looks at both local and local config files.

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
    _global_config_file: pathlib.Path = pathlib.Path.home().joinpath(".simvue.toml")
    _global_config = SimvueConfiguration(**toml.load(_global_config_file))
    _profiles = _global_config.profiles | _config.profiles

    try:
        _default_profile: str = urllib.parse.urlparse(_config.server.url).hostname
    except AttributeError:
        raise RuntimeError(f"Could not parse default URL '{_config.server.url}'")

    if not profile_name or profile_name == _default_profile:
        return None, _config.server

    for name, profile in _profiles.items():
        if profile_name == name:
            return name, profile
        try:
            _hostname: str = urllib.parse.urlparse(profile.url).hostname
        except AttributeError:
            raise RuntimeError(f"Could not parse default URL '{profile.url}'")
        if profile_name == _hostname:
            return name, profile
    raise ValueError(f"No such profile '{profile_name}'.")
