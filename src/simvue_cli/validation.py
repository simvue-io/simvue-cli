"""
Simvue CLI Click Validators
===========================

Custom types towards input validation
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import typing
import json
import re
import regex
import humanfriendly

import click

from click.core import Context, Parameter
from simvue.models import FOLDER_REGEX, NAME_REGEX


class TimeIntervalType(click.ParamType):
    name: str = "time_interval"

    @typing.override
    def convert(
        self, value: typing.Any, param: Parameter | None, ctx: Context | None
    ) -> typing.Any:
        try:
            return int(humanfriendly.parse_timespan(value) / 60 / 60)
        except humanfriendly.InvalidTimespan:
            self.fail(f"Failed to parse time interval '{value}'.")
        except Exception as e:
            self.fail(f"{e}")


class PatternMatch(click.ParamType):
    name: str = "text"

    def __init__(self, regex: re.Pattern[str]) -> None:
        self._pattern = re.compile(regex)

    def convert(
        self,
        value: typing.Literal["show-only"] | str,
        param: Parameter | None,
        ctx: Context | None,
    ) -> str:
        if value == "show-only":
            return value
        if not self._pattern.match(value):
            self.fail(
                f"'{value}' did not match regular expression '{self._pattern.pattern}'"
            )
        return value


class JSONParamType(click.ParamType):
    def __init__(self) -> None:
        self.name = "json_string"

    def convert(self, value: str, param: Parameter | None, ctx: Context | None) -> dict:
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            self.fail(f"Failed to load '{value}', invalid JSON string: {e}")
        except Exception as e:
            self.fail(f"{e}")


class FullNameType(click.ParamType):
    name: str = "text"

    def convert(
        self,
        value: typing.Literal["show-only"] | str,
        param: Parameter | str,
        ctx: Context | None,
    ) -> str:
        if value == "show-only":
            return value
        _name_regex = regex.compile(r"^\p{L}[\p{L}\p{M}'-]+(?: \p{L}[\p{L}\p{M}'-]+)*$")
        if not _name_regex.match(value):
            self.fail(f"'{value}' is not a valid full name")
        return value


SimvueFolder = PatternMatch(FOLDER_REGEX)
SimvueName = PatternMatch(NAME_REGEX)
FullName = FullNameType()
JSONType = JSONParamType()
Email = PatternMatch(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
UserName = PatternMatch(r"^[a-zA-Z0-9\-\_\.]+$")
TimeInterval = TimeIntervalType()
