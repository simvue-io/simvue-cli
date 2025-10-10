import dataclasses
import datetime
import more_itertools
import typing
import pydantic
import abc
import json
import pathlib
import simvue.api.objects as sv_obj
from simvue.api.objects.base import ObjectBatchArgs, VisibilityBatchArgs
from simvue.api.objects.run import RunBatchArgs
from simvue.models import FOLDER_REGEX, DATETIME_FORMAT, MetricSet

from simvue_cli.push.validate import Metadata

PUSHABLE_OBJECTS: set[str] = {"run"}
BATCH_RUN_LIMIT: int = 20_000


@dataclasses.dataclass
class PushAPI(abc.ABC):
    _data: dict[str, list[ObjectBatchArgs]] = dataclasses.field(init=False)
    _visibility: VisibilityBatchArgs = dataclasses.field(
        default_factory=VisibilityBatchArgs
    )
    _folder: str | None = None
    _metadata: dict[str, float | bool | str] = dataclasses.field(default_factory=dict)
    _run_metrics: dict[int, list[MetricSet]] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        self._data = {k: [] for k in PUSHABLE_OBJECTS}

    @pydantic.validate_call
    def tenant_visible(self, is_visible: bool) -> None:
        self._visibility.tenant = is_visible

    @pydantic.validate_call
    def public_visible(self, is_visible: bool) -> None:
        self._visibility.public = is_visible

    @pydantic.validate_call
    def visible_to_users(self, user_list: set[str]) -> None:
        self._visibility.user = list(user_list)

    @pydantic.validate_call
    def use_folder(
        self,
        folder_path: typing.Annotated[
            str, pydantic.StringConstraints(pattern=FOLDER_REGEX)
        ],
    ) -> None:
        self._folder = folder_path

    @pydantic.validate_call
    def global_metadata(self, metadata: str | dict[str, object]) -> None:
        if isinstance(metadata, str):
            metadata: Metadata = json.loads(metadata)
        self._metadata = metadata

    def add_run(
        self,
        *,
        folder: str,
        name: str | None = None,
        description: str | None = None,
        metadata: Metadata | None = None,
        metrics: list[dict[str, float | int]] | None = None,
        status: typing.Literal[
            "completed", "failed", "lost", "terminated"
        ] = "completed",
    ) -> None:
        _run = RunBatchArgs(
            name=name,
            folder=folder,
            metadata=metadata,
            description=description,
            status=status,
        )

        _index: int = len(self._data["run"])
        self._data["run"].append(_run)

        if metrics:
            _timestamp: str = datetime.datetime.now(datetime.UTC).strftime(
                DATETIME_FORMAT
            )
            self._run_metrics[_index] = [
                MetricSet(
                    time=metric_values.get("time", 0),
                    timestamp=metric_values.get("timestamp", _timestamp),
                    step=metric_values.get("step", i),
                    values=metric_values.get("values", metric_values),
                )
                for i, metric_values in enumerate(metrics)
            ]

    def push(self) -> None:
        if not (_run_data := self._data.get("run")):
            return

        def _queue_generator(data=_run_data):
            for item in more_itertools.chunked(data, BATCH_RUN_LIMIT):
                yield from sv_obj.Run.batch_create(
                    entries=item,
                    visibility=self._visibility,
                    folder=self._folder,
                    metadata=self._metadata,
                )

        for i, _id in enumerate(_queue_generator()):
            if _metrics := self._run_metrics.get(i):
                sv_obj.Metrics.new(run=_id, metrics=_metrics).commit()

    @abc.abstractmethod
    def load(self, input_file: pathlib.Path, *, folder: str, **_) -> None:
        pass

    @abc.abstractmethod
    def load_from_metadata(self, input_file: pathlib.Path, *, folder: str, **_) -> None:
        pass
