import simvue
import click
import typing
import pydantic
import subprocess
import multiprocessing
import multiparser
import datetime
import yaml

from simvue_cli.session.config.schema import (
    SessionConfiguration,
    Step,
    Status,
    Simulation,
    TrackedFile,
)
from simvue_cli.session.exception import SessionAbort


class Workflow(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=False,
        frozen=True,
        use_enum_values=True,
        validate_return=True,
        validate_default=True,
        extra="forbid",
    )
    config: SessionConfiguration
    offline: bool = False
    _session_id: str | None = pydantic.PrivateAttr(
        datetime.datetime.now(datetime.UTC).strftime("%d_%m_%y_%H_%M_%S_%f")
    )

    @classmethod
    @pydantic.validate_call
    def from_file(
        cls, session_file: pydantic.FilePath, offline: bool = False
    ) -> typing.Self:
        _config = yaml.load(session_file.open(), Loader=yaml.SafeLoader)
        return cls(offline=offline, config=_config)

    def _run_simvue_step(self, step: Simulation) -> Simulation:
        _init_args: dict[str, str | int | dict | bool] = self.config.options.model_dump(
            warnings="error"
        ) | step.options.model_dump(warnings="error")
        _config = dict(
            enable_emission_metrics=_init_args.pop("enable_emission_metrics"),
            disable_resource_metrics=_init_args.pop("disable_resource_metrics"),
            system_metrics_interval=_init_args.pop("system_metrics_interval"),
            abort_on_alert=_init_args.pop("abort_on_alert"),
            queue_blocking=_init_args.pop("queue_blocking"),
            suppress_errors=_init_args.pop("suppress_errors"),
        )
        _folder: str = f"{step.folder or ''}/{self._session_id}"
        _step_trigger = multiprocessing.Event()
        with simvue.Run(mode="offline" if self.offline else "online") as sv_run:
            sv_run.init(
                name=step.label,
                folder=_folder,
                tags=step.tags,
                description=step.description,
                **_init_args,
            )
            sv_run.config(**_config)
            _inputs: list[TrackedFile] = step.inputs or []
            _outputs: list[TrackedFile] = step.outputs or []
            for input in _inputs:
                sv_run.save_file(input, category="input", name=input.name)

            with multiparser.FileMonitor(
                termination_trigger=_step_trigger,
                per_thread_callback=lambda data, _: sv_run.log_metrics(data),
            ) as file_monitor:
                sv_run.add_process(
                    identifier=f"execute_{step.name}",
                    *step.arguments,
                    executable=step.executable,
                    script=step.script,
                    cwd=step.working_directory,
                    env=step.environment,
                    completion_trigger=_step_trigger,
                )
                for output in _outputs:
                    file_monitor.track(
                        path_glob_exprs=f"{output.path}",
                        static=output.static,
                    )
                file_monitor.run()
            for output in _outputs:
                sv_run.save_file(output, category="output", name=output.name)

    def _execute(self, step: Step) -> Step:
        if step.status == Status.Waiting and step.inputs:
            raise RuntimeError(
                f"Failed to find required inputs for next pending step '{step.label}'"
            )
        if step.status == Status.Completed:
            return step
        if isinstance(step, Simulation):
            return self._run_simvue_step(step)

        _command = step.arguments

        if step.executable:
            _command = [step.executable] + _command

        _result = subprocess.Popen(
            _command,
            env=step.environment,
            cwd=step.working_directory,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            text=True,
        )

        _cmd_out, _ = _result.communicate()

        step._return_code = _result.returncode
        step._return_output = _cmd_out

        if _result.returncode != 0:
            raise SessionAbort

        return step

    def play(self) -> typing.Generator[Step, None, None]:
        for i, step in enumerate(self.config.steps):
            try:
                yield self._execute(step)
            except SessionAbort:
                return
            finally:
                click.echo(f"[{i + 1}/{len(self.config.steps)}]")
                click.echo(step)
