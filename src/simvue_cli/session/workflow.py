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
    File
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
        _config["session_file"] = session_file
        return cls(offline=offline, config=_config)

    def _run_simvue_step(self, step: Simulation) -> Simulation:
        _init_args: dict[str, str | int | dict | bool] = self.config.options.model_dump(
            warnings="error"
        ) | step.options.model_dump(warnings="error")
        _config = dict(
            enable_emission_metrics=_init_args.pop("enable_emission_metrics", None),
            disable_resources_metrics=_init_args.pop("disable_resources_metrics", None),
            system_metrics_interval=_init_args.pop("system_metrics_interval", None),
            abort_on_alert=_init_args.pop("abort_on_alert", None),
            queue_blocking=_init_args.pop("queue_blocking", None),
            suppress_errors=_init_args.pop("suppress_errors", None),
            storage_id=_init_args.pop("storage_id", None)
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
            _inputs: list[File] = step.inputs or []
            _outputs: list[File] = step.outputs or []
            for input in _inputs:
                sv_run.save_file(input, category="input", name=input.name)

            with multiparser.FileMonitor(
                termination_trigger=_step_trigger,
                per_thread_callback=lambda data, _: sv_run.log_metrics(data),
            ) as file_monitor:
                sv_run.add_process(
                    f"execute_{step.label}",
                    *step.arguments,
                    executable=step.executable,
                    script=step.script,
                    cwd=step.working_directory,
                    env=step.environment,
                    completion_callback=lambda *_, **__: _step_trigger.set(),
                )
                for parsible in step.parse or []:
                    parsible.attach_to_monitor(file_monitor)
                file_monitor.run()
            for output in _outputs:
                sv_run.save_file(f"{output.path}", category="output", name=output.name)
            step._return_code = sv_run._executor.exit_status
            step._return_output = sv_run._executor.std_out(f"execute_{step.label}")
        return step

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
