"""Validation for CLI inputs."""

from csv import DictReader
from typing import Annotated
import pydantic

from simvue.models import NAME_REGEX, FOLDER_REGEX, MetadataKeyString, MetricKeyString

MetadataList = list[dict[MetadataKeyString, int | float | str]]


class JsonMetadataUpload(pydantic.BaseModel):
    metadata: MetadataList


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
