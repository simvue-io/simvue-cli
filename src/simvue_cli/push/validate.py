"""Validation for CLI inputs."""

import contextlib
from csv import DictReader
from typing import Annotated
import pydantic

from simvue.models import NAME_REGEX, FOLDER_REGEX, MetadataKeyString, MetricKeyString


def convert_data(value: str | float | int) -> str | float | int:
    """Convert numeric values from string to number."""
    if not isinstance(value, str):
        return value
    if value.count(".") == 1:
        with contextlib.suppress(ValueError):
            value = float(value)
    else:
        with contextlib.suppress(ValueError):
            value = int(value)
    return value


Metadata = dict[
    MetadataKeyString,
    Annotated[int | float | str, pydantic.BeforeValidator(convert_data)],
]


class MetadataUpload(pydantic.BaseModel):
    metadata: list[Metadata]


class JsonRun(pydantic.BaseModel):
    name: Annotated[str, pydantic.StringConstraints(pattern=NAME_REGEX)]
    description: Annotated[str, pydantic.StringConstraints(min_length=1)] | None = None
    metadata: dict[MetadataKeyString, object] = pydantic.Field(default_factory=dict)
    folder: Annotated[str, pydantic.StringConstraints(pattern=FOLDER_REGEX)] | None = (
        None
    )
    metrics: dict[MetricKeyString, int | float] = pydantic.Field(default_factory=dict)


class JsonRunUpload(pydantic.BaseModel):
    runs: list[JsonRun]
    folder: Annotated[str, pydantic.StringConstraints(pattern=FOLDER_REGEX)] | None = (
        None
    )
    metadata: dict[MetadataKeyString, object] = pydantic.Field(default_factory=dict)
