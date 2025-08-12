import tempfile
import time
import re
import pathlib
import typing
import pytest
import uuid
import os
import simvue
from simvue.api.objects import Alert, Run, Events, Storage, Tenant, User
from simvue.exception import ObjectNotFoundError
from simvue.run import UserAlert
import simvue_cli.actions



@pytest.mark.parametrize(
    "object", ("runs", "tag", "folders", "users", "tenants", "storages", "artifacts")
)
def test_object_list(create_plain_run, object) -> None:
    assert next(getattr(simvue_cli.actions, f"get_{object}_list")(count=10, sort_by=["created"], reverse=False))


def test_run_deletion(request) -> None:
    with simvue.Run() as run:
        fix_use_id: str = str(uuid.uuid4()).split('-', 1)[0]
        _test_name: str = request.node.name.replace("[", "_").replace("]", "")
        TEST_DATA = {
            "event_contains": "sent event",
            "metadata": {
                "test_engine": "pytest",
                "test_identifier": f"{_test_name}_{fix_use_id}"
            },
            "folder": f"/simvue_cli_testing/{fix_use_id}",
            "tags": ["simvue_cli_testing", _test_name], 
        }
        run.init(
            name=_test_name,
            tags=TEST_DATA["tags"],
            folder=TEST_DATA["folder"],
            visibility="tenant" if os.environ.get("CI") else None,
            retention_period="5 minutes",
            timeout=15,
            no_color=True
        )
    time.sleep(1)
    simvue_cli.actions.delete_run(run.id)


def test_user_alerts() -> None:
    _alert_name: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = simvue_cli.actions.create_user_alert(
        name=f"cli_alert_{_alert_name}",
        trigger_abort=True,
        email_notify=False,
        description=None
    )
    assert _alert.id
    assert _alert.id in (a[0] for a in simvue_cli.actions.get_alerts_list(sort_by=["created"], reverse=False))
    simvue_cli.actions.delete_alert(alert_id=_alert.id)
    with pytest.raises(ObjectNotFoundError):
        Alert(identifier=_alert.id)


def test_create_run_and_log() -> None:
    _run_name: str = f"{uuid.uuid4()}".split("-")[0]
    _run = simvue_cli.actions.create_simvue_run(
        tags=["simvue_cli", "test_run_create"],
        name=_run_name,
        folder="/simvue_cli_tests",
        retention=60,
        running=True,
        timeout=10,
        environment=False,
        description="Simvue CLI test run create"
    )
    assert _run.id
    simvue_cli.actions.log_metrics(
        run_id=_run.id,
        metrics={"x": 1, "y": 2}
    )
    simvue_cli.actions.log_event(run_id=_run.id, event_message="Hello world!")

    assert any("x" in m[0] for m in _run.metrics)
    assert any("y" in m[0] for m in _run.metrics)
    assert any("Hello world!" in i.message for i in Events.get(run_id=_run.id))

    # Retrieve run
    assert simvue_cli.actions.get_run(run_id=_run.id).id
    simvue_cli.actions.set_run_status(run_id=_run.id, status="lost")
    with pytest.raises(ValueError) as e:
        simvue_cli.actions.set_run_status(run_id=_run.id, status="completed")
    assert e.match(r"status is")
    simvue_cli.actions.delete_run(run_id=_run.id)
    time.sleep(1)
    with pytest.raises(ObjectNotFoundError):
        Run(identifier=_run.id)
    with pytest.raises(ValueError) as e:
        simvue_cli.actions.set_run_status(run_id=_run.id, status="completed")
    assert e.match(r"does not exist")



def test_get_server_version() -> None:
    assert re.findall(r"\d+\.\d+\.\d+", (_server_version := f"{simvue_cli.actions.get_server_version()}")), f"Got {_server_version} for server version"


@pytest.mark.unix
def test_storage() -> None:
    name = "simvue_cli_test_storage"
    endpoint_url="https://not-a-real-url.io"
    region_name="fictionsville"
    access_key_id="dummy_key"
    secret_access_key="not_a_key"
    bucket="dummy_bucket"
    is_enabled=False

    with tempfile.NamedTemporaryFile() as temp_f:
        with open(temp_f.name, "w") as out_f:
            out_f.write("not_a_key")

        with open(temp_f.name) as in_f:
            _storage = simvue_cli.actions.create_simvue_s3_storage(
                name=name,
                endpoint_url=endpoint_url,
                disable_check=True,
                default=False,
                access_key_id=access_key_id,
                region_name=region_name,
                bucket=bucket,
                access_key_file=in_f,
                block_tenant=True,
                disable=True
            )
        assert _storage.id
        assert _storage.id in (a[0] for a in simvue_cli.actions.get_storages_list())
        simvue_cli.actions.delete_storage(storage_id=_storage.id)
        assert _storage.id not in (a[0] for a in Storage.get())


def test_user_and_tenant_creation() -> None:
    _tenant_name = "simvue_cli_tenant"
    _user_name = "jbloggs"
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    _tenant = simvue_cli.actions.create_simvue_tenant(
        max_request_rate=1,
        max_runs=1,
        max_data_volume=1,
        name=f"{_tenant_name}_{_uuid}",
        disabled=True,
    )
    assert _tenant.id
    _user = simvue_cli.actions.create_simvue_user(
        username=_user_name,
        full_name="Joe Bloggs",
        email="jbloggs@simvue.io",
        tenant=_tenant.id,
        disabled=True,
        read_only=True,
        admin=False,
        manager=False,
        welcome=False,
    )
    assert _user.id

    simvue_cli.actions.delete_user(_user.id)

    assert _user.id not in (a[0] for a in User.get())

    simvue_cli.actions.delete_tenant(_tenant.id)

    assert _tenant.id not in (a[0] for a in Tenant.get())


def test_run_abort(create_test_run, monkeypatch) -> None:
    _run, _ = create_test_run
    simvue_cli.actions.set_run_status(
        _run.id, "terminated", "test CLI abort"
    )
    time.sleep(1)
    assert _run._sv_obj.status == "terminated"
    assert _run._status == "terminated"


def test_run_artifact_download(create_test_run) -> None:
    _, _ = create_test_run
    _run, _data = create_test_run

    with tempfile.TemporaryDirectory() as temp_d:
        _out_dir = pathlib.Path(temp_d)
        _files = simvue_cli.actions.pull_run(_run.id, output_dir=_out_dir)
        _basenames = [f.name for f in _out_dir.joinpath(_data["folder"][1:]).glob("*")]
        assert all(f.name in _basenames for f in _files)
        assert all(_data[f"file_{i}"] in _basenames for i in range(1, 4))


@pytest.mark.parametrize(
    "status", ("ok", "critical")
)
def test_user_alert_triggered(create_plain_run: tuple[simvue.Run, dict], status: typing.Literal["ok", "critical"]) -> None:
    run, _ = create_plain_run
    _alert_id = run.create_user_alert(
        name="test_user_alert_triggered_alert",
        description="Test alert for CLI triggering",
        trigger_abort=True
    )
    simvue_cli.actions.trigger_user_alert(
        run.id,
        _alert_id,
        status
    )
    _alert: UserAlert = Alert(_alert_id)
    assert _alert.get_status(run.id) == status

