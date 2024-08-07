"""
Simvue Configuration
====================

Functionality for updating configuration of Simvue API via the CLI
"""
import pathlib
import configparser

SIMVUE_CONFIG_FILENAME: str = "simvue.ini"


def set_configuration_option(section: str, key: str, value: str | int | float, local: bool) -> pathlib.Path:
    """Set a configuation value for Simvue"""
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

