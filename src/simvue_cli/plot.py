"""Plot Simvue Metrics Locally."""

import plotext as plt

from collections.abc import Generator


def plot_simvue_metrics(
    *,
    plot_iterator: Generator[tuple[str, str, list[float], list[float]]],
    time_label: str,
    marker_x_coord: float | None = None,
    marker_y_coord: float | None = None,
    single_metric: bool = False,
    single_run: bool = False,
    show_plot: bool = True,
) -> str:
    _metric_label: str | None = None
    for metric_name, run_id, x_values, y_values in plot_iterator:
        _legend_label: list[str] = []
        if not single_metric:
            _legend_label.append(metric_name)
            _metric_label = metric_name
        if not single_run:
            _legend_label.append(run_id)
        _legend_label_str: str | None = (
            "-".join(_legend_label) if _legend_label else None
        )
        plt.plot(x_values, y_values, label=_legend_label_str)
    plt.plotsize(500, 500)
    plt.xlabel(time_label)
    if _metric_label:
        plt.ylabel(_metric_label)
    if marker_x_coord:
        plt.vertical_line(marker_x_coord)
    if marker_y_coord:
        plt.horizontal_line(marker_y_coord)
    if show_plot:
        plt.show()
    return plt.build()
