import json
import re
import typing

from .base import ParserDefinition

class JSON(ParserDefinition):
    parser: typing.Literal["json"] = "json"
    mode: typing.Literal["track"] = "track"
    def _parse_file(self, input_file: str, **_) -> tuple[dict[str, object], list[dict[str, int | float | bool]]]:
        _out = [row for row in json.load(open(input_file))]
        if self.tracked_values:
            _out = [
                {k: v for k, v in row.items() if any(re.match(k, tracked) for tracked in self.tracked_values)}
                for row in _out
            ]
        return {}, json.load(open(input_file))
    
    def _parse_log(self, _: str, **__) -> tuple[dict[str, object], list[dict[str, int | bool | float]]]:
        raise NotImplementedError("Log parsing is not supported for type JSON.")