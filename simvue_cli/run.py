"""
Simvue CLI run
==============

Handles creation of and maintaining of runs between CLI calls
"""

import pathlib
import uuid
import json
import typing
import msgpack
import time

import simvue.api as sv_api

from datetime import datetime, timezone

from simvue.factory.proxy import Simvue

from simvue.run import get_system
from simvue.client import Client

# Local directory to hold run information
CACHE_DIRECTORY = pathlib.Path().home().joinpath(".simvue", "cli_runs")


def _check_run_exists(run_id: str) -> pathlib.Path:
    run_shelf_file = CACHE_DIRECTORY.joinpath(f"{run_id}.json")
    if not (run := Client().get_run(run_id)):
        if run_shelf_file.exists():
            run_shelf_file.unlink()
        raise ValueError(f"Run '{run_id}' does not exist.")

    if (status := run.get("status")) in ("lost", "terminated", "completed", "failed"):
        if run_shelf_file.exists():
            run_shelf_file.unlink()
        raise ValueError(f"Run '{run_id}' status is '{status}'.")
    return run_shelf_file


def create_simvue_run(
    tags: list[str] | None,
    running: bool,
    description: str | None,
    name: str | None,
    folder: str,
    timeout: int | None,
) -> None:
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
    """
    run_name, run_id = Simvue(
        None, uniq_id=f"{uuid.uuid4()}", mode="online"
    ).create_run(
        data={
            "tags": tags or [],
            "status": "running" if running else "created",
            "ttl": None,
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

    Simvue(None, uniq_id=run_id, mode="online").send_metrics(
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

    Simvue(None, uniq_id=run_id, mode="online").send_event(
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

    Simvue(name=None, uniq_id=run_id, mode="online").update(
        data={"status": status} | kwargs
    )

    if status in ("completed", "lost", "failed", "terminated"):
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
    run_shelf_file = _check_run_exists(run_id)

    Simvue(name=None, uniq_id=run_id, mode="online").update(
        data={"metadata": metadata} | kwargs
    )


def get_server_version() -> None:
    simvue_instance = Simvue(name=None, uniq_id="", mode="online")
    response = sv_api.get(
        f"{simvue_instance._url}/api/version", headers=simvue_instance._headers
    )
    return response.json().get("version")


def get_runs_list(**kwargs) -> None:
    """Retrieve list of Simvue runs"""
    client = Client()
    runs = client.get_runs(**kwargs)
    return runs


def get_run(run_id: str) -> None:
    """Retrieve a Run from the Simvue server"""
    client = Client()
    return client.get_run(run_id)


def get_alerts(**kwargs) -> None:
    """Retrieve list of Simvue alerts"""
    client = Client()
    alerts = client.get_alerts()


def create_user_alert(name: str, trigger_abort: bool, email_notify: bool) -> None:
    """Create a User alert"""
    alert_data = {
        "name": name,
        "source": "user",
        "abort": trigger_abort,
        "notification": "email" if email_notify else "none",
    }
    Simvue(name=None, uniq_id="undefined", mode="online").add_alert(alert_data)
