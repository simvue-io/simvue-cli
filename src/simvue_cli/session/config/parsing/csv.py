import pathlib
import re
import typing
import pydantic

from .base import ParserDefinition


class CSV(ParserDefinition):
    parser: typing.Literal["csv"] = "csv"
    headers: list[str] | None = pydantic.Field(
        None, description="Specify headers for each column manually"
    )
    header_line_index: pydantic.NonNegativeInt | None = pydantic.Field(
        0, description="Index of line defining headers, if None, no headers present."
    )
    pattern: typing.Pattern[str] | None = pydantic.Field(
        None, description="Pattern defining lines to be recorded."
    )
    _cache: dict[str, int | None | list[str]] = pydantic.PrivateAttr(
        {"log_index": 0, "headers": None}
    )

    def _parse_file(
        self, input_file: str, **_
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        import csv

        with pathlib.Path(input_file).open() as in_f:
            _lines = in_f.readlines()
            if self.header_line_index:
                _lines = _lines[self.header_line_index :]
            if self.pattern:
                _lines = [line for line in _lines if re.match(self.pattern, line)]
        _out = [row for row in csv.DictReader(_lines)]
        return {}, self._filter_tracked(_out)

    def _parse_log(
        self, file_content: str, **_
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        import csv

        _lines = file_content.split("\n")

        if (
            self.header_line_index
            and self._cache["log_index"] + len(_lines) < self.header_line_index
        ):
            return {}, {}

        if self.header_line_index and self._cache["log_index"] < self.header_line_index:
            _lines = _lines[self.header_line_index :]

        if self.pattern:
            _lines = [line for line in _lines if re.match(self.pattern, line)]

        if not _lines:
            return {}, {}

        self._cache["log_index"] += len(_lines)
        _csv_reader = csv.DictReader(_lines)

        if _headers := self.headers or self._cache["headers"]:
            _out = [
                {h: v for h, v in zip(_headers, row.values())}
                for row in csv.DictReader(_lines)
            ]
        elif not _csv_reader.fieldnames:
            raise RuntimeError("Failed to deduce headers for CSV file.")
        else:
            self._cache["headers"] = list(_csv_reader.fieldnames)
            _out = [row for row in _csv_reader]

        if self.tracked_values:
            _out = [
                {
                    k: v
                    for k, v in row.items()
                    if any(re.match(tracked, k) for tracked in self.tracked_values)
                }
                for row in _out
            ]

        return {}, _out
