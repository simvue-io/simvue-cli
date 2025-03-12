import time
import pytest
import uuid
import simvue_cli.actions



@pytest.mark.parametrize(
    "object", ("runs", "tag", "folders")
)
def test_object_list(create_plain_run, object) -> None:
    assert next(getattr(simvue_cli.actions, f"get_{object}_list")())


def test_run_deletion(create_plain_run) -> None:
    _run, _ = create_plain_run
    simvue_cli.actions.delete_run(_run.id)


def test_get_alerts(create_test_run) -> None:
    assert next(simvue_cli.actions.get_alerts())

def test_user_alert_creation() -> None:
    _alert_name: str = f"{uuid.uuid4()}".split("-")[0]
    simvue_cli.actions.create_user_alert(
        name=f"cli_alert_{_alert_name}",
        trigger_abort=True,
        email_notify=False,
        description=None
    )


def test_create_run() -> None:
    _run_name: str = f"{uuid.uuid4()}".split("-")[0]
    simvue_cli.actions.create_simvue_run(
        tags=["simvue_cli", "test_run_create"],
        name=_run_name,
        folder="/simvue_cli_tests",
        retention=60 * 60,
        running=True,
        timeout=10,
        description="Simvue CLI test run create"
    )


def test_run_abort(create_test_run) -> None:
    _run, _ = create_test_run
    simvue_cli.actions.set_run_status(
        _run.id, "terminated", "test CLI abort"
    )
    time.sleep(1)
    assert _run._sv_obj.status == "terminated"
    assert _run._status == "terminated"
