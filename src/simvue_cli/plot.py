"""Plot Simvue Metrics Locally."""

import datetime
import plotext as plt

from collections.abc import Generator
from simvue.models import DATETIME_FORMAT, typing


def plot_simvue_metrics(
    *,
    plot_iterator: Generator[tuple[str, str, list[float | str], list[float]]],
    time_label: str,
    marker_x_coord: float | str | None = None,
    marker_y_coord: float | None = None,
    single_metric: bool = False,
    single_run: bool = False,
) -> None:
    """Plot a set of metrics in the terminal."""
    _metric_label: str | None = None
    _run_label: str | None = None
    plt.clear_figure()
    plt.xlabel(time_label)
    plt.date_form("H:M:S")
    for metric_name, run_id, x_values, y_values in plot_iterator:
        _legend_label: list[str] = []
        _metric_label = metric_name
        _run_label = run_id
        if time_label == "timestamp":
            x_values = [
                datetime.datetime.strptime(
                    typing.cast("str", val), f"{DATETIME_FORMAT}Z"
                ).strftime("%H:%M:%S")
                for val in x_values
            ]
        if not single_metric:
            _legend_label.append(metric_name)
        if not single_run:
            _legend_label.append(run_id)
        _legend_label_str: str | None = (
            "-".join(_legend_label) if _legend_label else None
        )
        plt.plot(x_values, y_values, label=_legend_label_str)
    if single_metric and single_run and _run_label and _metric_label:
        plt.title(f"{_metric_label} for Run {_run_label}")
    elif single_run and _run_label:
        plt.title(_run_label)
    elif single_metric and _metric_label:
        plt.title(_metric_label)
    if single_metric:
        plt.ylabel(_metric_label)
    if marker_x_coord:
        plt.vertical_line(marker_x_coord)
    if marker_y_coord:
        plt.horizontal_line(marker_y_coord)
    plt.show()
