from simvue.factory.proxy import typing
import tabulate
import click

STATUS_FORMAT: dict[str, str] = {
    "running": "blue",
    "failed": "red",
    "completed": "green",
    "lost": "yellow",
    "created": "white",
    "N/A": "grey",
}

CLICK_COLORS: dict[str, str] = {
    "red": "white",
    "green": "black",
    "yellow": "black",
    "blue": "white",
    "magenta": "black",
    "cyan": "black",
    "bright_red": "white",
    "bright_green":"black",
    "bright_yellow": "black",
    "bright_blue": "white",
    "bright_magenta": "black",
    "bright_cyan": "black",
}


def format_status(status: str, plain_text: bool, *_, **__) -> str:
    if plain_text:
        return status
    return click.style(status, fg=STATUS_FORMAT[status], bold=True)


def format_tags(
    tags: list[str], plain_text: bool, out_config: dict[str, dict[str, typing.Any]]
) -> str:
    out_config["tags"] = out_config.get("tags") or {}

    if plain_text:
        return ", ".join(tags)

    tag_out: list[str] = []

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

    return ", ".join(tag_out)


COLUMN_FORMAT: dict[str, typing.Callable[[str | list[str]], str]] = {
    "status": format_status,
    "tags": format_tags,
}


def create_runs_display(
    columns: list[str],
    runs: list[dict[str, typing.Any]],
    plain_text: bool,
    enumerate_: bool,
    format: str | None,
) -> str:
    table_headers = [
        click.style(c, bold=True) if not plain_text else c
        for c in (("#", *columns) if enumerate_ else columns)
    ]

    contents: list[list[str]] = []
    out_config: dict[str, dict[str, typing.Any]] = {}

    for i, run in enumerate(runs):
        row: list[str] = []
        if enumerate_:
            row.append(str(i))

        for column in columns:
            value = run.get(column, "N/A")
            if formatter := COLUMN_FORMAT.get(column):
                row.append(formatter(value, plain_text, out_config))
            else:
                row.append(value)
        contents.append(row)

    if not format:
        runs_list: list[str] = ["\t".join(c) for c in contents]
        return "\n".join(runs_list)

    return tabulate.tabulate(contents, headers=table_headers, tablefmt=format).__str__()
