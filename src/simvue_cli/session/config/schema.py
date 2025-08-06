import pydantic
import tempfile
import os
import pathlib
import typing
import enum
import click
import re
import shutil

from simvue_cli.session import workflow

from .parsing import ParserType

FOLDER_REGEX: str = r"^/.*"
NAME_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:]+$"


class Status(enum.Enum):
    Completed = enum.auto()
    Waiting = enum.auto()
    Ready = enum.auto()
    Failed = enum.auto()


class Mode(enum.StrEnum):
    Track = "track"
    Tail = "tail"


class File(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=False,
        frozen=True,
        use_enum_values=True,
        validate_return=True,
        validate_default=True,
        extra="forbid",
    )
    name: typing.Annotated[str, pydantic.constr(pattern=NAME_REGEX)] | None = None
    path: pathlib.Path

    def __hash__(self) -> int:
        return f"{self.name}{self.path}".__hash__()


class Step(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=False,
        frozen=True,
        use_enum_values=True,
        validate_return=True,
        validate_default=True,
        extra="forbid",
    )
    description: str = pydantic.Field(..., description="Description for this step")
    label: str | None = pydantic.Field(
        None,
        pattern=NAME_REGEX,
        description="Default name for Simvue runs, if unspecified workflow name is used.",
    )
    executable: pydantic.FilePath | None = pydantic.Field(
        None, description="Location of executable for simulation."
    )
    shell: str | None = pydantic.Field(
        None, description="Use the specified shell to run the arguments."
    )
    script: pathlib.Path | None = pydantic.Field(
        None, description="Script to be executed."
    )
    arguments: list[str] = pydantic.Field(
        default_factory=list, description="Arguments to command."
    )
    inputs: list[File] | None = pydantic.Field(
        None, description="Required input files in working directory."
    )
    outputs: list[File] | None = pydantic.Field(
        None, description="Created output files in working directory."
    )
    environment: dict[str, str | int | float | None] | None = pydantic.Field(
        None, description="Environment variables to set."
    )
    working_directory: pydantic.DirectoryPath = pydantic.Field(
        pathlib.Path(__file__).parent,
        description="Working directory for the simulation.",
    )
    _temporary_file: pathlib.Path | None = pydantic.PrivateAttr(None)
    _return_code: int | None = pydantic.PrivateAttr(None)
    _return_output: str | None = pydantic.PrivateAttr(None)

    @property
    def user_script(self) -> pathlib.Path | None:
        return self.script or self._temporary_file

    @pydantic.model_validator(mode="before")
    @classmethod
    def check_shell_or_executable(cls, values: dict[str, object]) -> dict[str, object]:
        if not values.get("shell") and not values.get("executable"):
            raise ValueError(
                f"Must provide argument 'shell' or 'executable' for step '{values['label']}"
            )
        if not values.get("script") and not values.get("arguments"):
            raise ValueError(
                f"Must provide argument 'script' or 'arguments' for step '{values['label']}'"
            )
        return values

    @pydantic.field_validator("executable", mode="before")
    @classmethod
    def convert_to_path(
        cls, executable: pathlib.Path | str | None
    ) -> pathlib.Path | str | None:
        if not executable:
            return executable
        _expanded = os.path.expanduser(executable)
        _expanded = os.path.expandvars(_expanded)
        if not pathlib.Path(f"{_expanded}").exists() and (
            path_str := shutil.which(f"{executable}")
        ):
            return pathlib.Path(path_str)
        return executable

    @pydantic.field_validator("arguments", mode="before")
    @classmethod
    def expand_arguments(cls, arguments: list[str]) -> list[str]:
        return [os.path.expanduser(os.path.expandvars(arg)) for arg in arguments]

    @property
    def status(self) -> Status:
        """Determine state of state."""
        _inputs: list[pathlib.Path] = self.inputs or []
        _outputs: list[pathlib.Path] = self.outputs or []

        if self._return_code:
            return Status.Failed

        if not self.inputs:
            return Status.Waiting

        if not all(_input.path.exists() for _input in _inputs):
            return Status.Waiting

        if not all(_output.path.exists() for _output in _outputs):
            return Status.Ready

        return Status.Completed

    def __str__(self) -> str:
        _font_color = "blue"
        if self._return_code is not None:
            _font_color = "red" if self._return_code else "green"
        _command: str = " ".join(self.arguments) if self.arguments else ""
        _command: str = "\n\t     ".join([f"{c};" for c in _command.split(";")])
        _command: str = _command if self.arguments else ""
        return click.style(
            f"""
***************************************************************************
Label       : {self.label}{"\nShell       : " + str(self.shell) if self.shell else ""}
Command     : {str(self.executable) + " " if self.executable else ""}{_command}
Inputs      : {", ".join([str(f.path) for f in self.inputs or []])}
Outputs     : {", ".join([str(f.path) for f in self.outputs or []])}{"\nReturn Code : " + str(self._return_code) if self._return_code is not None else ""}
***************************************************************************{"\n\n" + self._return_output if self._return_output is not None else ""}
""",
            fg=_font_color,
            bold=True,
        )

    def clean(self) -> None:
        if self.script:
            self.script.unlink()


class Options(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=False,
        frozen=True,
        use_enum_values=True,
        validate_return=True,
        validate_default=True,
        extra="forbid",
    )
    enable_emission_metrics: bool = False
    disable_resources_metrics: bool = False
    retention_period: (
        typing.Annotated[
            str, pydantic.StringConstraints(strip_whitespace=True, to_lower=True)
        ]
        | None
    ) = pydantic.Field(None, description="Maximum retention period for runs.")
    visibility: typing.Literal["public", "tenant"] | list[str] | None = pydantic.Field(
        None, description="Set run visibility."
    )
    no_color: bool = False
    notification: typing.Literal["none", "all", "error", "lost"] = "none"
    timeout: int | None = None
    queue_blocking: bool | None = None
    system_metrics_interval: pydantic.PositiveInt | None = None
    storage_id: str | None = None
    abort_on_alert: typing.Literal["run", "all", "ignore"] | bool | None = None
    queue_blocking: bool | None = None
    suppress_errors: bool | None = None


class Simulation(Step):
    options: Options = pydantic.Field(
        default_factory=Options, description="Options for this session"
    )
    parse: list[ParserType]
    metadata: dict[str, str] | None = pydantic.Field(
        None, description="Metadata to attach to this simulation."
    )
    tags: typing.Annotated[list[str], pydantic.conset(str)] | None = pydantic.Field(
        None, description="Tags to assign to this session."
    )
    folder: (
        typing.Annotated[str, pydantic.StringConstraints(pattern=FOLDER_REGEX)] | None
    ) = None


class SessionConfiguration(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=False,
        frozen=True,
        use_enum_values=True,
        validate_return=True,
        validate_default=True,
        extra="forbid",
    )
    session_file: pydantic.FilePath = pydantic.Field(
        ..., description="Path to the session YAML file."
    )
    workflow: str = pydantic.Field(..., description="Name for this workflow")
    label: str | None = pydantic.Field(
        None,
        pattern=NAME_REGEX,
        description="Default name for Simvue runs, if unspecified workflow name is used.",
    )
    metadata: dict[str, str] | None = pydantic.Field(
        None, description="Metadata to attach to session."
    )
    steps: list[Step | Simulation] = pydantic.Field(
        ..., description="Steps to execute for this session."
    )
    tags: typing.Annotated[list[str], pydantic.conset(str)] | None = pydantic.Field(
        None, description="Tags to assign to this session."
    )
    options: Options = pydantic.Field(
        default_factory=Options, description="Options for this session"
    )

    @pydantic.model_validator(mode="before")
    @classmethod
    def set_default_name(cls, values: dict[str, str]) -> dict[str, str]:
        if values.get("label") is None:
            values["label"] = values["workflow"].replace(" ", "_")
        for character in values["label"]:
            if not re.match(r"[\w\d_]", character):
                values["label"] = values["label"].replace(character, "")
        return values

    @pydantic.field_validator("session_file", mode="before")
    @classmethod
    def _get_session_file_path(cls, session_file: pathlib.Path) -> pathlib.Path:
        _expanded = os.path.expanduser(f"{session_file}")
        _expanded = os.path.expandvars(_expanded)
        return pathlib.Path(_expanded)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _parse_special_variables(cls, values: dict[str, object]) -> dict[str, object]:
        """Parse any strings for recognised special variables."""
        _mapping: dict[str, str] = {
            "${{ session_file }}": f"{values['session_file']}",
            "${{ session_dir }}": f"{pathlib.Path(values['session_file']).parent}",
        }
        for i, step in enumerate(values["steps"]):
            for j, input_file in enumerate(step.get("inputs", [])):
                _path: str = f"{input_file['path']}"
                for key, value in _mapping.items():
                    _path = _path.replace(key, value)
                values["steps"][i]["inputs"][j]["path"] = pathlib.Path(_path)
            for j, parse_entry in enumerate(step.get("parse", [])):
                _path: str = f"{parse_entry['path']}"
                for key, value in _mapping.items():
                    _path = _path.replace(key, value)
                values["steps"][i]["parse"][j]["path"] = pathlib.Path(_path)
            for j, output_file in enumerate(step.get("outputs", [])):
                _path: str = f"{output_file['path']}"
                for key, value in _mapping.items():
                    _path = _path.replace(key, value)
                values["steps"][i]["outputs"][j]["path"] = pathlib.Path(_path)
            for j, argument in enumerate(step.get("arguments", [])):
                _argument = argument
                for key, value in _mapping.items():
                    _argument = _argument.replace(key, value)
                values["steps"][i]["arguments"][j] = _argument
        return values

    @pydantic.model_validator(mode="after")
    def _create_temporary_files(self) -> "SessionConfiguration":
        for step in self.steps:
            if step.executable:
                continue

            with tempfile.NamedTemporaryFile(
                delete=False,
                prefix=f"{step.label}",
                suffix=".sh",
            ) as out_f:
                with open(out_f.name, "w") as out_file:
                    out_file.write(" ".join(step.arguments or []))
                step._temporary_file = out_file.name
        return self
