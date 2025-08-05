import pathlib
import pydantic
import re
from .base import ParserDefinition, TrackedLabelledValue


class Generic(ParserDefinition):
    tracked_values: list[TrackedLabelledValue] = pydantic.Field(
        ...,
        description="Regular expressions defining which values to track within the log file, by default None",
    )
    convert: bool = pydantic.Field(
      True, description="Perform smart conversion of values."
    )

    def _parse_file(
        self, input_file: str, **_
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:

        with pathlib.Path(input_file).open() as in_f:
            _lines = in_f.readlines()

        return {}, self._parse_lines(_lines)
    
    def _parse_lines(self, lines: list[str]) -> list[dict[str, int | float | bool]]:
        _recorded: list[dict[str, int | float | bool]] = []

        for line in lines:
            _line_data: dict[str, int | float | bool] = {}
            for tracked_value in self.tracked_values:
                if value := re.findall(tracked_value.pattern, line):
                    _line_data[tracked_value.label] = self._convert_value(value[0])
            _recorded.append(_line_data)
        return _recorded

    def _parse_log(
        self, file_content: str, **_
    ) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        return {}, self._parse_lines(file_content.split("\n"))
