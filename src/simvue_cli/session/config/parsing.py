import pathlib
import re
import typing
import pydantic
import abc
import multiparser.parsing.file as mp_file
import multiparser.parsing.tail as mp_log


class ParserDefinition(abc.ABC):
    @abc.abstractmethod
    @mp_file.file_parser
    def track_parser_function(
        self, input_file: str, **_
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        pass

    @abc.abstractmethod
    @mp_log.log_parser
    def log_parser_function(
        self, file_content: str, **_
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        pass


class CSV(pydantic.BaseModel, ParserDefinition):
    header_line_index: pydantic.NonNegativeInt | None = pydantic.Field(
        0, description="Index of line defining headers, if None, no headers present."
    )
    pattern: typing.Pattern[str] | None = pydantic.Field(
        None, description="Pattern defining lines to be recorded."
    )
    _cache: dict[str, object] = pydantic.PrivateAttr({"log_index": 0})

    def track_parser_function(
        self, input_file: str, **_
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        import csv

        with pathlib.Path(input_file).open() as in_f:
            _lines = in_f.readlines()
            if self.header_line_index:
                _lines = _lines[self.header_line_index :]
            if self.pattern:
                _lines = [line for line in _lines if re.match(line)]
        return {}, [row for row in csv.DictReader(_lines)]

    def log_parser_function(
        self, file_content: str, **_:with
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        import csv

        _lines = file_content.split("\n")
        _offset = self._cache["log_index"]
        if self.header_line_index and (self.header_line_index - self._cache["log_index"]) > 0:
            _lines = _lines[self.header_line_index :]
        if self.pattern:
            _lines = [line for line in _lines if re.match(line)]
        self._cache["log_index"] += len(_lines)
        return {}, [row for row in csv.DictReader(_lines)]
