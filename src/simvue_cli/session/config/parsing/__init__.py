from .csv import CSV
from .generic import Generic
from .json import JSON

import typing

__all__ = [
    "CSV",
    "Generic",
    "JSON"
]

ParserType = typing.Union[CSV, Generic, JSON]