from simvue.factory.proxy import typing
import tabulate
import click

STATUS_FORMAT: dict[str, str] = {
    "running": "blue",
    "failed": "red",
    "completed": "green",
    "lost": "yellow",
    "created": "white",
    "N/A": "grey"
}


def format_status(status: str, plain_text: bool) -> str:
    if plain_text:
        return status
    return click.style(status, fg=STATUS_FORMAT[status], bold=True)


COLUMN_FORMAT: dict[str, typing.Callable[[str], str]] = {
    "status": format_status
}


def create_runs_display(columns: list[str], runs: dict[str, typing.Any], plain_text: bool, enumerate_: bool, format: str | None) -> str:

    table_headers = [
        click.style(c, bold=True) if not plain_text else c
        for c in (("#", *columns) if enumerate_ else columns)
    ]

    contents: list[list[str]] = []

    for i, run in enumerate(runs):
        row: list[str] = []
        if enumerate_:
            row.append(i)

        for column in columns:
            value = run.get(column, "N/A")
            if (formatter := COLUMN_FORMAT.get(column)):
                row.append(formatter(value, plain_text))
            else:
                row.append(value)
        contents.append(row)

    if not format:
        runs_list: list[list[str]] = [
            "\t".join(c) for c in contents
        ]
        return "\n".join(runs_list)

    return tabulate.tabulate(contents, headers=table_headers, tablefmt=format).__str__()

