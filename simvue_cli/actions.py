"""
Simvue CLI Actions
==================

Contains callbacks for CLI commands
"""

__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import pathlib
import json
import typing
import time
import toml
import venv
import shutil
import subprocess

import click
import simvue.api.request as sv_api
import simvue.metadata as sv_meta

from datetime import datetime, timezone

from simvue.run import Artifact, get_system
from simvue.api.objects.alert.base import AlertBase
from simvue.api.objects import (
    Alert,
    Run,
    Tag,
    Folder,
    UserAlert,
    Metrics,
    Storage,
    Stats,
)
from simvue.api.objects.administrator import User, Tenant

from .config import get_url_and_headers

# Local directory to hold run information
CACHE_DIRECTORY = pathlib.Path().home().joinpath(".simvue", "cli_runs")


def _check_run_exists(run_id: str) -> tuple[pathlib.Path, Run]:
    """Check if the given run exists on the server

    If the run is found to not exist then any local files representing it
    are removed. The same applies if the run is no longer active.
    """
    run_shelf_file = CACHE_DIRECTORY.joinpath(f"{run_id}.json")

    try:
        run = Run(identifier=run_id)
    except StopIteration:
        if run_shelf_file.exists():
            run_shelf_file.unlink()
        raise ValueError(f"Run '{run_id}' does not exist.")

    if (status := run.status) in ("lost", "terminated", "completed", "failed"):
        if run_shelf_file.exists():
            run_shelf_file.unlink()
        raise ValueError(f"Run '{run_id}' status is '{status}'.")

    # If the run was created by other means, need to make a local cache file
    # retrieve last time step, and the start time of the run
    if not run_shelf_file.exists():
        out_data = {"step": 0, "start_time": time.time()}
        if step := max(metric.get("step", 0) for _, metric in run.metrics or {}):
            out_data["step"] = step
        if time_now := min(metric.get("time", 0) for _, metric in run.metrics or {}):
            out_data["start_time"] = time_now
        with run_shelf_file.open("w") as out_f:
            json.dump(out_data, out_f)

    return run_shelf_file, run


def create_simvue_run(
    tags: list[str] | None,
    running: bool,
    description: str | None,
    name: str | None,
    folder: str,
    timeout: int | None,
    retention: int | None,
    environment: bool,
) -> str | None:
    """Create and initialise a new Simvue run

    Parameters
    ----------

    tags : list[str] | None
        a set of tags to assign to this run
    running : bool
        whether this run should be started or left in the created state
    description : str | None
        a short description for the run
    name : str | None
        a name to assign to this run
    folder : str
        folder path for this run
    timeout : int | None
        timout of run
    retention : int | None
        retention period in seconds
    environment : bool
        include environment in metadata

    Returns
    -------

    str | None
        Simvue run ID if successful else None
    """
    if folder != "/":
        try:
            _folder = Folder.new(path=folder)
            _folder.commit()
        except RuntimeError as e:
            if "status 409" not in e.args[0]:
                raise e
    _run = Run.new(folder=folder)

    _run.tags = tags or []
    _run.status = "running" if running else "created"
    _run.ttl = retention
    _run.description = description
    _run.system = get_system()

    if environment:
        _run.metadata = sv_meta.environment()
    if name:
        _run.name = name
    _run.commit()
    _id = _run.id
    _name = _run.name

    if not CACHE_DIRECTORY.exists():
        CACHE_DIRECTORY.mkdir(parents=True)

    with CACHE_DIRECTORY.joinpath(f"{_id}.json").open("w") as out_f:
        json.dump(
            {"id": _id, "name": _name, "start_time": time.time(), "step": 0},
            out_f,
            indent=2,
        )

    return _id


def log_metrics(run_id: str, metrics: dict[str, int | float]) -> None:
    """Log metrics for a given run

    Parameters
    ----------

    run_id : str
        identifier for the target run
    metrics : dict[str, int | float]
        a dictionary containing metrics to be sent

    """
    run_shelf_file, run = _check_run_exists(run_id)

    run_data = json.load(open(run_shelf_file))

    metrics_list: list[dict] = [
        {
            "values": metrics,
            "time": time.time() - run_data["start_time"],
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "step": run_data["step"],
        }
    ]

    _metrics = Metrics.new(run_id=run.id, metrics=metrics_list)
    _metrics.commit()

    with open(run_shelf_file, "w") as out_f:
        run_data["step"] += 1
        json.dump(run_data, out_f, indent=2)


def log_event(run_id: str, event_message: str) -> None:
    """Log an event for a given run

    Parameters
    ----------

    run_id : str
        identifier for the target run
    event_message : str
        the message to be displayed

    """
    _, run = _check_run_exists(run_id)

    events_list: list[dict] = [
        {
            "message": event_message,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
        }
    ]

    run.log_entries("events", events_list)


def set_run_status(run_id: str, status: str, reason: str | None = None) -> None:
    """Update the status of a Simvue run

    Parameters
    ----------

    run_id : str
        unique identifier for the target run
    status : str
        the new status for this run

    """
    run_shelf_file, run = _check_run_exists(run_id)
    run.read_only(False)
    if status == "terminated" and reason:
        run.abort(reason)
    else:
        run.status = status
        run.commit()

    if status in {"completed", "lost", "failed", "terminated"}:
        run_shelf_file.unlink()


def update_metadata(run_id: str, metadata: dict[str, typing.Any]) -> None:
    """Update the metadata of a Simvue run

    Parameters
    ----------

    run_id : str
        unique identifier for the target run
    metadata : dict
        the new status for this run

    """
    _, run = _check_run_exists(run_id)
    run.metadata = metadata
    run.commit()


def get_server_version() -> typing.Union[str, int]:
    """Retrieve the version of the Simvue server running at the configured endpoint

    If the version cannot be retrieved the response status is returned instead.

    Returns
    -------
    str | int
        either the version of the server as a string, or the status code of the
        failed HTTP request
    """
    _url, _headers = get_url_and_headers()
    response = sv_api.get(f"{_url}/api/version", headers=_headers)
    if response.status_code != 200:
        return response.status_code

    return response.json().get("version")


def user_info() -> dict:
    """Retrieve information on the current Simvue user fromt he server

    Returns
    -------
    dict
        the JSON response from the 'whoami' request to the Simvue server
    """
    return Stats().whoami()


def get_runs_list(**kwargs) -> typing.Generator[tuple[str, Run], None, None]:
    """Retrieve list of Simvue runs"""
    return Run.get(**kwargs)


def get_tag_list(**kwargs) -> None:
    """Retrieve list of Simvue tags"""
    return Tag.get(**kwargs)


def get_storages_list(**kwargs) -> typing.Generator[tuple[str, Storage], None, None]:
    """Retrieve list of Simvue storages"""
    return Storage.get(**kwargs)


def get_storage_list(**kwargs) -> None:
    """Retrieve list of Simvue storages"""
    return Storage.get(**kwargs)


def get_folders_list(**kwargs) -> None:
    """Retrieve list of Simvue runs"""
    return Folder.get(**kwargs)


def get_tenants_list(**kwargs) -> typing.Generator[tuple[str, Tenant], None, None]:
    """Retrieve list of Simvue tenants"""
    return Tenant.get(**kwargs)


def get_users_list(**kwargs) -> typing.Generator[tuple[str, User], None, None]:
    """Retrieve list of Simvue users"""
    return User.get(**kwargs)


def get_artifacts_list(**kwargs) -> typing.Generator[tuple[str, Artifact], None, None]:
    """Retrieve list of Simvye artifacts"""
    return Artifact.get(**kwargs)


def get_run(run_id: str) -> Run:
    """Retrieve a Run from the Simvue server"""
    return Run(identifier=run_id)


def delete_run(run_id: str) -> None:
    """Delete a given run from the Simvue server"""
    _run = get_run(run_id)
    _run.delete()


def delete_storage(storage_id: str) -> None:
    """Delete a given storage from the Simvue server"""
    _storage = get_storage(storage_id)
    _storage.delete()


def get_alerts(**kwargs) -> typing.Generator[AlertBase, None, None]:
    """Retrieve list of Simvue alerts"""
    return Alert.get(**kwargs)


def create_user_alert(
    name: str, trigger_abort: bool, email_notify: bool, description: str | None
) -> Alert:
    """Create a User alert

    Parameters
    ----------
    name : str
        name to allocate this alert
    trigger_abort : bool
        whether triggering of this alert will terminate the relevant simulation
    email_notify : bool
        whether trigger of this alert will send an email to the creator
    description : str | None
        a description for this alert

    Returns
    -------
    dict | None
        server response on alert creation
    """
    _alert = UserAlert.new(
        name=name,
        notification="email" if email_notify else "none",
        description=description,
    )
    _alert.abort = trigger_abort
    _alert.commit()
    return _alert


def create_simvue_user(
    username: str,
    email: str,
    full_name: str,
    manager: bool,
    admin: bool,
    disabled: bool,
    read_only: bool,
    tenant: str,
    welcome: bool,
) -> str:
    """Create a new Simvue user on the server.

    Parameters
    ----------
    username : str
        username for this user
    email : str
        contact email for the user
    full_name : str
        given name and surname for the user
    manager : bool
        assign the manager role to this user
    admin : bool
        assign the admin role to this user
    disabled : bool
        whether the user is disabled on creation
    read_only : bool
        give only read-only access to this user
    tenant : str
        the tenant to assign this user to
    welcome : bool
        display welcome message


    Returns
    -------
    str
        the unique identifier for the user
    """
    _user = User.new(
        username=username,
        fullname=full_name,
        email=email,
        manager=manager,
        admin=admin,
        readonly=read_only,
        enabled=not disabled,
        tenant=tenant,
        welcome=welcome,
    )
    _user.commit()

    return _user.id


def create_simvue_tenant(
    name: str,
    disabled: bool,
    max_runs: int,
    max_request_rate: int,
    max_data_volume: int,
) -> str:
    """Create a Tenant on the simvue server.

    Parameters
    ----------
    name : str
        name for this tenant
    disabled : bool
        disable this tenant on creation
    max_runs : int
        maximum number of runs for this tenant
    max_request_rate : int
        maximum number of requests for this tenant
    max_data_volume : int
        maximum data volume for this tenant

    Returns
    -------
    str
        the unique identifer for the user
    """
    _tenant = Tenant.new(
        name=name,
        enabled=not disabled,
        max_request_rate=max_request_rate or 0,
        max_runs=max_runs or 0,
        max_data_volume=max_data_volume or 0,
    )
    _tenant.commit()
    return _tenant.id


def get_tenant(tenant_id: str) -> Tenant:
    """Retrieve a tenant from the server"""
    return Tenant(identifier=tenant_id)


def get_folder(folder_id: str) -> Folder:
    """Retrieve a folder from the server"""
    return Folder(identifier=folder_id)


def get_tag(tag_id: str) -> Tag:
    """Retrieve a tag from the server"""
    return Tag(identifier=tag_id)


def get_storage(storage_id: str) -> Storage:
    """Retrieve a storage from the server"""
    return Storage(identifier=storage_id)


def get_user(user_id: str) -> User:
    """Retrieve a user from the server"""
    return User(identifier=user_id)


def delete_tenant(tenant_id: str) -> None:
    """Delete a given tenant from the Simvue server"""
    _tenant = get_tenant(tenant_id)
    _tenant.delete()


def delete_user(user_id: str) -> None:
    """Delete a given user from the Simvue server"""
    _user = get_user(user_id)
    _user.delete()


def create_environment(
    language: typing.Literal["python", "rust", "julia", "javascript"],
    venv_directory: str,
    run: str,
    allow_existing: bool,
) -> None:
    _run = get_run(run)
    if not (_venv_def := _run.metadata.get(language, {}).get("environment")):
        raise RuntimeError(
            f"Run '{_run.id}' does not have an environment of type '{language}'"
        )

    _venv_dir = pathlib.Path(venv_directory)

    if language == "python":
        _pip_bin = _venv_dir.joinpath("bin", "pip")
        if _venv_dir.exists() and (not _pip_bin.exists() or not allow_existing):
            raise FileExistsError(
                "Cannot create environment, directory already exists!"
            )
        elif _pip_bin.exists():
            click.echo("Installing dependencies into existing environment.")
        else:
            venv.create(env_dir=venv_directory, with_pip=True, upgrade_deps=True)
        _command: list[str] = [f"{_pip_bin}", "install", "--isolated", "--no-cache-dir"]

        for dependency, version in _venv_def.items():
            try:
                subprocess.run(args=_command + [f"{dependency}=={version}"])
            except subprocess.CalledProcessError as e:
                click.echo(
                    f"Warning: Failed to install '{dependency}=={version}': {e.args[0]}"
                )

    elif language == "rust":
        if not (_cargo_path := shutil.which("cargo")):
            raise FileNotFoundError(
                "Cargo must be installed on this system to create Rust environments."
            )
        _toml_file = _venv_dir.joinpath("Cargo.toml")
        if _venv_dir.exists() and (not _toml_file.exists() or not allow_existing):
            raise FileExistsError(
                "Cannot create environment, directory already exists!"
            )
        if _venv_dir.exists():
            _toml_data = toml.load(_toml_file)
            _dependencies = _toml_data.get("dependencies", {})
        else:
            _venv_dir.mkdir()
            _venv_dir.joinpath("src").mkdir()
            _venv_dir.joinpath("src", "main.rs").touch()
            _toml_data = {
                "package": {"name": "new_project", "version": "0.1.0"},
            }
            _dependencies = {}

        _dependencies |= _venv_def
        _toml_data["dependencies"] = _dependencies

        toml.dump(_toml_data, _toml_file.open("w"))

        subprocess.run([_cargo_path, "build"], cwd=venv_directory)
