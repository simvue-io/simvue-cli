"""
Simvue CLI run
==============

Handles creation of and maintaining of runs between CLI calls
"""

import pathlib
import uuid
import json
import msgpack
import time

from datetime import datetime, timezone

from simvue.factory.proxy import Simvue

from simvue.run import get_system
from simvue.client import Client

# Local directory to hold run information
CACHE_DIRECTORY = pathlib.Path().home().joinpath(".simvue", "cli_runs")


def _check_run_exists(run_id: str) -> pathlib.Path:
    if not (run_shelf_file := CACHE_DIRECTORY.joinpath(f"{run_id}.json")).exists():
        raise ValueError(f"Run '{run_id}' does not exist or has terminated.")
    return run_shelf_file


def create_simvue_run(
    tags: list[str] | None, running: bool, description: str | None, name: str | None, folder: str
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
            "folder": folder
        }
    )

    if not CACHE_DIRECTORY.exists():
        CACHE_DIRECTORY.mkdir(parents=True)

    with CACHE_DIRECTORY.joinpath(f"{run_id}.json").open("w") as out_f:
        json.dump({"id": run_id, "name": run_name, "start_time": time.time(), "step": 0}, out_f, indent=2)

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
            "step": run_data["step"]
        }
    ]

    Simvue(None, uniq_id=run_id, mode="online").send_metrics(
        msgpack.packb({"metrics": metrics_list, "run": run_id}, use_bin_type=True)
    )

    with open(run_shelf_file, "w") as out_f:
        run_data["step"] += 1
        json.dump(run_data, out_f, indent=2)


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

    Simvue(name=None, uniq_id=run_id, mode="online").update(data={"status": status} | kwargs)

    run_shelf_file.unlink()


def get_runs_list(**kwargs) -> None:
    client = Client()
    runs = client.get_runs(**kwargs)
    return runs
