"""
Simvue Configuration
====================

Functionality for updating configuration of Simvue API via the CLI
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import json
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
    local: bool | None = None,
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
    local : bool | None, optional
        whether to modify the global or local Simvue configuration
        if None modify first found

    Returns
    -------
    pathlib.Path
        path to the modified configuration file
    """

    _first_config_file = SimvueConfiguration.fetch(mode="offline").config_file()
    _global_config_file = pathlib.Path().home().joinpath(f".{SIMVUE_CONFIG_FILENAME}")
    _config_file: pathlib.Path | None = None

    if local and _first_config_file == _global_config_file:
        raise ValueError("Argument 'local' set but no local configuration file found.")

    if local or local is None:
        _config_file = _first_config_file
    else:
        _config_file = _global_config_file

    config = toml.load(_config_file) if _config_file.exists() else {}

    if not config.get(section):
        config[section] = {}

    config[section][key] = value

    toml.dump(config, _config_file.open("w", encoding="utf-8"))

    return _config_file


def set_profile_option(profile_name: str | None, key: str, value: str) -> pathlib.Path:
    """Modify profile setting."""
    _config_file = SimvueConfiguration.fetch(mode="offline").config_file()
    _config: SimvueConfiguration = toml.load(_config_file)
    _global_config_file: pathlib.Path = pathlib.Path.home().joinpath(
        f".{SIMVUE_CONFIG_FILENAME}"
    )
    _global_config = toml.load(_global_config_file)

    if not profile_name:
        return set_configuration_option("server", key=key, value=value)

    for name, profile in (
        (_config_profiles := _config.get("profiles", {}))
        | (_global_config_profiles := _global_config.get("profiles", {}))
    ).items():
        try:
            _hostname: str = urllib.parse.urlparse(profile["url"]).hostname
        except AttributeError as e:
            raise RuntimeError(f"Could not parse default URL '{profile['url']}'")
        if profile_name == name or profile_name == _hostname:
            if name in _config_profiles:
                _config_profiles[name][key] = value
                with _config_file.open("w") as out_f:
                    toml.dump(_config, out_f)
                return _config_file
            else:
                _global_config_profiles[name][key] = value
                with _global_config_file.open("w") as out_f:
                    toml.dump(_global_config, out_f)
                return _global_config_file
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
        except AttributeError as e:
            raise RuntimeError(f"Could not parse default URL '{profile.url}'")
        if profile_name == _hostname:
            return name, profile
    raise ValueError(f"No such profile '{profile_name}'.")
