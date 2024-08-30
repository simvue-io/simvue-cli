"""
Simvue CLI Click Validators
===========================

Custom types towards input validation
"""
import typing
import re

import click

from click.core import Context, Parameter
from simvue.models import FOLDER_REGEX, NAME_REGEX
from simvue.run import json


class PatternMatch(click.ParamType):
    def __init__(self, regex: typing.Pattern[str]) -> None:
        self._pattern = re.compile(regex)
        self.name = 'pattern_match'

    def convert(self, value: str, param: Parameter | None, ctx: Context | None) -> str:
        if not self._pattern.match(value):
            self.fail(f"'{value}' did not match regular expression '{self._pattern.pattern}'")
        return value


class JSONParamType(click.ParamType):
    def __init__(self) -> None:
        self.name = "json_string"

    def convert(self, value: str, param: Parameter | None, ctx: Context | None) -> dict:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            self.fail(f"Failed to load '{value}', invalid JSON string")


SimvueFolder = PatternMatch(FOLDER_REGEX)
SimvueName = PatternMatch(NAME_REGEX)
JSONType = JSONParamType()

