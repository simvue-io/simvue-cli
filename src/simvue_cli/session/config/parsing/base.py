import abc
import pydantic
import re
import typing
import pathlib
import multiparser.parsing.file as mp_file
import multiparser.parsing.tail as mp_log

if typing.TYPE_CHECKING:
    from multiparser import FileMonitor


class TrackedValue(pydantic.BaseModel):
    pattern: typing.Pattern[str]


class TrackedLabelledValue(TrackedValue):
    label: str = pydantic.Field(..., description="Label to assign to this value.")


class ParserDefinition(pydantic.BaseModel):
    path: pathlib.Path
    tracked_values: list[TrackedValue | TrackedLabelledValue] | None = pydantic.Field(
        None,
        description="Regular expressions defining which values to track within the log file, by default None",
    )
    static: bool = pydantic.Field(False, description="Parse this file once only.")
    mode: typing.Literal["track", "tail"] = pydantic.Field(
        "track",
        description="Parse mode, either full file per update, or tail the file.",
    )

    @abc.abstractmethod
    def _parse_file(
        self, input_file: str, **kwargs: object
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        pass

    @abc.abstractmethod
    def _parse_log(
        self, file_content: str, **_: object
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        pass

    @mp_log.log_parser
    def log_parser_function(
        self, file_content: str, **kwargs: object
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        return self._parse_log(file_content, **kwargs)

    @mp_file.file_parser
    def track_parser_function(
        self, input_file: str, **kwargs: object
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        return self._parse_file(input_file, **kwargs)

    @staticmethod
    def _convert_value(value: str) -> int | float | bool:
        if re.match(r"-*\d+\.*\d*e*E*-*\d*", value):
            return float(value)
        if re.match(r"true|True|False|false", value):
            return bool(value)
        if re.match(r"\w*", value):
            raise ValueError(f"Invalid metric value '{value}'")
        if re.match(r"d+", value):
            return int(value)
        raise RuntimeError(f"Failed to convert value '{value}'")

    def _filter_tracked(
        self, recorded: list[dict[str, str]]
    ) -> list[dict[str, int | float | bool]]:
        if not self.tracked_values:
            return [
                {k: self._convert_value(v) for k, v in row.items()} for row in recorded
            ]

        _filtered: list[dict[str, str]] = []
        for row in recorded:
            _row_metrics: dict[str, int | float | bool] = {}
            _find_metric: bool = True
            for k, v in row.items():
                for tracked in self.tracked_values:
                    if re.match(tracked.pattern, k):
                        _label = tracked.label if isinstance(tracked, TrackedLabelledValue) else k
                        _row_metrics[_label] = self._convert_value(v)
                        _find_metric = False
                        break
                if not _find_metric:
                    break
            _filtered.append(_row_metrics)
        return _filtered
    
    def attach_to_monitor(self, file_monitor: "FileMonitor") -> None:
        if self.mode == "tail":
            file_monitor.tail(
                path_glob_exprs=f"{self.path}",
                parser_func=self.track_parser_function
            )
        else:
            print(f"Attached {self.path} monitor")
            file_monitor.track(
                path_glob_exprs=f"{self.path}",
                static=self.static,
                parser_func=self.track_parser_function
            )
