"""
Simvue CLI Display

Contains functions to aid in the display of information.
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

from simvue.api.objects.base import SimvueObject

import tabulate
import typing
import click
from pydantic_extra_types.color import RGBA

SIMVUE_LOGO: str = """

                                             *****
                                            ******
          *****                              ****
      *************
    ***  ******   ***        ************    *****    **************   *********    **            **   **           **         *******
      ***   *    *  **      *************    *****    ***************************    **           *    **           **       **       **
     ** **    ***    **    *****             *****    ******     *******    ******    **         **    **           **     **           **
    ** **       ** * ***   **********        *****    *****      ******      *****     **       **     **           **     *            **
 *  ** **       **** ***     ************    *****    *****       *****      *****      **     **      **           **     ***************
     ** *       * ** ***           *******   *****    *****       *****      *****       **   **       **           **     **
  *  ***    ***  ** ***     ***      *****   *****    *****       *****      *****        *  **         **         ***     **
   **  ****  ****  ***     **************    *****    *****       *****      *****        ****           **       ****       ***      ***
     ***        *****        *********       *****    *****       *****      *****         **              ******   **          ******
       ***********
"""

STATUS_FORMAT: dict[str, str] = {
    "running": "blue",
    "failed": "red",
    "completed": "green",
    "lost": "yellow",
    "created": "white",
    "N/A": "grey",
    "terminated": "red",
}

CLICK_COLORS: dict[str, str] = {
    "red": "white",
    "green": "black",
    "yellow": "black",
    "blue": "white",
    "magenta": "black",
    "cyan": "black",
    "bright_red": "white",
    "bright_green": "black",
    "bright_yellow": "black",
    "bright_blue": "white",
    "bright_magenta": "black",
    "bright_cyan": "black",
}


def format_status(status: str, plain_text: bool, *_, **__) -> str:
    """Format Simvue server object status

    Parameters
    ----------
    status : str
        status to be formatted
    plain_text : bool
        whether to use color formatting

    Returns
    -------
    str
        either a click formatted string or original text
    """
    if plain_text:
        return status
    return click.style(status, fg=STATUS_FORMAT[status], bold=True)


def format_color(color: RGBA, *_, **__) -> str:
    return f"({color.r}, {color.g}, {color.b})"


def format_tags(
    tags: list[str], plain_text: bool, out_config: dict[str, dict[str, typing.Any]]
) -> str:
    """Format Simvue server object tags

    A configuration dictionary is used to define which color to use for each tag
    and to ensure that same color is used whenever the given tag is present.

    Parameters
    ----------
    tags : list[str]
        list of tags to display
    plain_text : bool
        whether to use color formatting
    out_config : dict[str, Any]
        configuration defining color selection

    Returns
    -------
    str
        either a click formatted string or original text
    """
    out_config["tags"] = out_config.get("tags") or {}

    if plain_text:
        return f"[{', '.join(tags)}]" if tags else ""

    tag_out: list[str] = []

    # Iterate through all tags selecting either the color for that
    # tag (if already defined) or allocating one
    for tag in tags:
        if not (color := out_config["tags"].get(tag)):
            for click_color in CLICK_COLORS:
                if click_color not in out_config["tags"].values():
                    color = click_color
                    break
            if not color:
                used_colors: list[str] = list(out_config["tags"].values())
                if len(used_colors) % len(CLICK_COLORS) == 0:
                    color = list(CLICK_COLORS.keys())[0]
                else:
                    frequency = {used_colors.count(c): c for c in used_colors}
                    color = frequency[min(frequency)]
            out_config["tags"][tag] = color
        tag_out.append(click.style(tag, fg=CLICK_COLORS[color], bg=color, bold=True))

    return " ".join(tag_out)


# Allocate functions to format each column type
COLUMN_FORMAT: dict[str, typing.Callable[[str | list[str]], str]] = {
    "status": format_status,
    "tags": format_tags,
    "color": format_color,
    "colour": format_color,
}


def create_objects_display(
    columns: list[str],
    objects: typing.Generator[tuple[str, SimvueObject], None, None],
    plain_text: bool,
    enumerate_: bool,
    format: str | None,
) -> str:
    """Create display for Simvue runs

    Creates either a plain BASH style argument list or a table of runs
    with options for how the table is displayed.

    Parameters
    ----------
    columns : list[str]
        list of columns to display from the given data
    objects: Generator[tuple[str, SimvueObject]]
        list of objects retrieved from the Simvue server
    plain_text : bool
        whether to use color formatting
    enumerate : bool
        whether to display a counter next to the runs
    format : str | None
        whether to display as a table or a single column list.
        If a string, this will be the format used by the tabulate
        module.

    Returns
    -------
    str
        either a click formatted string or original text
    """

    # Remove 'is_' prefix from relevant columns and format
    table_headers = [
        c.replace("is_", "")
        if plain_text
        else click.style(c.replace("is_", ""), bold=True)
        for c in (("#", *columns) if enumerate_ else columns)
    ]

    contents: list[list[str]] = []
    out_config: dict[str, dict[str, typing.Any]] = {}

    for i, (_, obj) in enumerate(
        sorted(objects, key=lambda x: getattr(x[1], "created", x[1].id), reverse=True)
    ):
        row: list[str] = []
        if enumerate_:
            row.append(str(i))

        for column in columns:
            # FIXME: Hack for if a property has not been added to the API yet
            if not (value := getattr(obj, column, None)):
                try:
                    value = obj._get_attribute(column)
                except KeyError:
                    value = "N/A"
            if formatter := COLUMN_FORMAT.get(column):
                row.append(formatter(value, plain_text, out_config))
            else:
                row.append(str(value))
        contents.append(row)

    if not format or plain_text:
        objs_list: list[str] = ["\t".join(c) for c in contents]
        return "\n".join(objs_list)

    return tabulate.tabulate(contents, headers=table_headers, tablefmt=format).__str__()
