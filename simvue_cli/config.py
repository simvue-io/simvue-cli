"""
Simvue Configuration
====================

Functionality for updating configuration of Simvue API via the CLI
"""
__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import pathlib
import configparser

SIMVUE_CONFIG_FILENAME: str = "simvue.ini"


def set_configuration_option(section: str, key: str, value: str | int | float, local: bool) -> pathlib.Path:
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

    config = configparser.ConfigParser()

    if file_name.exists():
        config.read(file_name)

    if not config.has_section(section):
        config.add_section(section)

    config.set(section, key, value)

    with file_name.open("w") as config_out:
        config.write(config_out)

    return file_name

