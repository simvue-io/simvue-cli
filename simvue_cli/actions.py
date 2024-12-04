"""
Simvue CLI Actions
==================

Contains callbacks for CLI commands
"""
__author__ = "Kristian Zarebski"
__date__ = "2024-09-09"

import pathlib
import uuid
import json
import typing
import msgpack
import time

import simvue.api as sv_api

from datetime import datetime, timezone

from simvue.factory.proxy import Simvue
from simvue.config.user import SimvueConfiguration

from simvue.run import get_system
from simvue.client import Client

# Local directory to hold run information
CACHE_DIRECTORY = pathlib.Path().home().joinpath(".simvue", "cli_runs")


def _check_run_exists(run_id: str) -> pathlib.Path:
    """Check if the given run exists on the server

    If the run is found to not exist then any local files representing it
    are removed. The same applies if the run is no longer active.
    """
    run_shelf_file = CACHE_DIRECTORY.joinpath(f"{run_id}.json")
    if not (run := Client().get_run(run_id)) or not isinstance(run, dict):
        if run_shelf_file.exists():
            run_shelf_file.unlink()
        raise ValueError(f"Run '{run_id}' does not exist.")

    if (status := run.get("status")) in ("lost", "terminated", "completed", "failed"):
        if run_shelf_file.exists():
            run_shelf_file.unlink()
        raise ValueError(f"Run '{run_id}' status is '{status}'.")

    # If the run was created by other means, need to make a local cache file
    # retrieve last time step, and the start time of the run
    if not run_shelf_file.exists():
        metrics = run["metrics"]

        if not isinstance(metrics, dict):
            raise RuntimeError(f"Expected metrics to be of type 'dict', but got '{metrics}'")
        out_data = {"step": 0, "start_time": time.time()}
        if metrics and (step := max(metric.get("step") for metric in metrics)):
            out_data["step"] = step
        if metrics and (time_now := min(metric.get("time") for metric in metrics)):
            out_data["start_time"] = time_now
        with run_shelf_file.open("w") as out_f:
            json.dump(out_data, out_f)

    return run_shelf_file


def create_simvue_run(
    tags: list[str] | None,
    running: bool,
    description: str | None,
    name: str | None,
    folder: str,
    timeout: int | None,
    retention: int | None,
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

    Returns
    -------

    str | None
        Simvue run ID if successful else None
    """
    run_name, run_id = Simvue(
        None, uniq_id=f"{uuid.uuid4()}", mode="online", config=SimvueConfiguration.fetch()
    ).create_run(
        data={
            "tags": tags or [],
            "status": "running" if running else "created",
            "ttl": retention,
            "name": name,
            "description": description,
            "system": get_system(),
            "folder": folder,
            "heartbeat_timeout": timeout,
        }
    )

    if not CACHE_DIRECTORY.exists():
        CACHE_DIRECTORY.mkdir(parents=True)

    with CACHE_DIRECTORY.joinpath(f"{run_id}.json").open("w") as out_f:
        json.dump(
            {"id": run_id, "name": run_name, "start_time": time.time(), "step": 0},
            out_f,
            indent=2,
        )

    return run_id


def log_metrics(run_id: str, metrics: dict[str, int | float]) -> None:
    """Log metrics for a given run

    Parameters
    ----------

    run_id : str
        identifier for the target run
    metrics : dict[str, int | float]
        a dictionary containing metrics to be sent

    """
    run_shelf_file = _check_run_exists(run_id)

    run_data = json.load(open(run_shelf_file))

    metrics_list: list[dict] = [
        {
            "values": metrics,
            "time": time.time() - run_data["start_time"],
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
            "step": run_data["step"],
        }
    ]

    Simvue(None, uniq_id=run_id, mode="online", config=SimvueConfiguration.fetch()).send_metrics(
        msgpack.packb({"metrics": metrics_list, "run": run_id}, use_bin_type=True)
    )

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
    _check_run_exists(run_id)

    events_list: list[dict] = [
        {
            "message": event_message,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
        }
    ]

    Simvue(None, uniq_id=run_id, mode="online", config=SimvueConfiguration.fetch()).send_event(
        msgpack.packb({"events": events_list, "run": run_id}, use_bin_type=True)
    )


def set_run_status(run_id: str, status: str, **kwargs) -> None:
    """Update the status of a Simvue run

    Parameters
    ----------

    run_id : str
        unique identifier for the target run
    status : str
        the new status for this run
    **kwargs : dict
        additional attributes required by the server to set the status

    """
    run_shelf_file = _check_run_exists(run_id)

    Simvue(name=None, uniq_id=run_id, mode="online", config=SimvueConfiguration.fetch()).update(
        data={"status": status} | kwargs
    )

    if status in {"completed", "lost", "failed", "terminated"}:
        run_shelf_file.unlink()


def update_metadata(run_id: str, metadata: dict[str, typing.Any], **kwargs) -> None:
    """Update the metadata of a Simvue run

    Parameters
    ----------

    run_id : str
        unique identifier for the target run
    metadata : dict
        the new status for this run
    **kwargs : dict
        additional attributes required by the server to set the status

    """
    _check_run_exists(run_id)

    Simvue(name=None, uniq_id=run_id, mode="online", config=SimvueConfiguration.fetch()).update(
        data={"metadata": metadata} | kwargs
    )


def get_server_version() -> typing.Union[str, int]:
    """Retrieve the version of the Simvue server running at the configured endpoint

    If the version cannot be retrieved the response status is returned instead.

    Returns
    -------
    str | int
        either the version of the server as a string, or the status code of the
        failed HTTP request
    """
    simvue_instance = Simvue(name=None, uniq_id="", mode="online", config=SimvueConfiguration.fetch())
    response = sv_api.get(
        f"{simvue_instance._config.server.url}/api/version", headers=simvue_instance._headers
    )
    if response.status_code != 200:
        return response.status_code

    return response.json().get("version")


def user_info() -> dict:
    """Retrieve information on the current Simvue user fromt he server

    Returns
    -------
    dict
        the JSON response from the 'whomai' request to the Simvue server
    """
    simvue_instance = Simvue(name=None, uniq_id="", mode="online", config=SimvueConfiguration.fetch())
    response = sv_api.get(
        f"{simvue_instance._config.server.url}/api/whoami", headers=simvue_instance._headers
    )
    return response.status_code if response.status_code != 200 else response.json()


def get_runs_list(**kwargs) -> None:
    """Retrieve list of Simvue runs"""
    client = Client()
    return client.get_runs(**kwargs)


def get_tag_list(**kwargs) -> None:
    """Retrieve list of Simvue tags"""
    client = Client()
    return client.get_tags(**kwargs)


def get_folders_list(**kwargs) -> None:
    """Retrieve list of Simvue runs"""
    client = Client()
    return client.get_folders(**kwargs)


def get_run(run_id: str) -> None:
    """Retrieve a Run from the Simvue server"""
    client = Client()
    return client.get_run(run_id)


def delete_run(run_id: str) -> None:
    """Delete a given run from the Simvue server"""
    client = Client()
    return client.delete_run(run_id)


def get_alerts(**kwargs) -> None:
    """Retrieve list of Simvue alerts"""
    #TODO: Implement alert listing
    client = Client()
    client.get_alerts()


def create_user_alert(name: str, trigger_abort: bool, email_notify: bool) -> dict | None:
    """Create a User alert

    Parameters
    ----------
    name : str
        name to allocate this alert
    trigger_abort : bool
        whether triggering of this alert will terminate the relevant simulation
    email_notify : bool
        whether trigger of this alert will send an email to the creator

    Returns
    -------
    dict | None
        server response on alert creation
    """
    alert_data = {
        "name": name,
        "source": "user",
        "abort": trigger_abort,
        "notification": "email" if email_notify else "none",
    }
    return Simvue(name=None, uniq_id="undefined", mode="online", config=SimvueConfiguration.fetch()).add_alert(alert_data)

