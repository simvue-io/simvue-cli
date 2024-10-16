import simvue.run as sv_run
import os
import uuid
import tempfile
import pytest
import time
import json
import typing

MAX_BUFFER_SIZE: int = 10

@pytest.fixture
def create_plain_run(request) -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    with sv_run.Run() as run:
        yield run, setup_test_run(run, False, request)


@pytest.fixture
def create_test_run(request) -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    with sv_run.Run() as run:
        yield run, setup_test_run(run, True, request)


def setup_test_run(run: sv_run.Run, create_objects: bool, request: pytest.FixtureRequest):
    fix_use_id: str = str(uuid.uuid4()).split('-', 1)[0]
    TEST_DATA = {
        "event_contains": "sent event",
        "metadata": {
            "test_engine": "pytest",
            "test_identifier": fix_use_id
        },
        "folder": f"/simvue_cli_testing/{fix_use_id}",
        "tags": ["simvue_cli_testing", request.node.name.replace("[", "_").replace("]", "_")]
    }

    if os.environ.get("CI"):
        TEST_DATA["tags"].append("ci")

    run.config(suppress_errors=False)
    run.init(
        name=f"test_run_{TEST_DATA['metadata']['test_identifier']}",
        tags=TEST_DATA["tags"],
        folder=TEST_DATA["folder"],
        visibility="tenant" if os.environ.get("CI") else None,
        retention_period="1 minute",
        timeout=15,
        no_color=True
    )
    run._dispatcher._max_buffer_size = MAX_BUFFER_SIZE

    if create_objects:
        for i in range(5):
            run.log_event(f"{TEST_DATA['event_contains']} {i}")

        for i in range(5):
            run.create_alert(name=f"alert_{i}", source="events", frequency=1, pattern=TEST_DATA['event_contains'])

        for i in range(5):
            run.log_metrics({"metric_counter": i, "metric_val": i*i - 1})

    run.update_metadata(TEST_DATA["metadata"])

    if create_objects:
        TEST_DATA["metrics"] = ("metric_counter", "metric_val")
    TEST_DATA["run_id"] = run._id
    TEST_DATA["run_name"] = run._name
    TEST_DATA["url"] = run._config.server.url
    TEST_DATA["headers"] = run._headers
    TEST_DATA["pid"] = run._pid
    TEST_DATA["resources_metrics_interval"] = run._resources_metrics_interval

    if create_objects:
        with tempfile.TemporaryDirectory() as tempd:
            with open((test_file := os.path.join(tempd, "test_file.txt")), "w") as out_f:
                out_f.write("This is a test file")
            run.save_file(test_file, category="input", name="test_file")
            TEST_DATA["file_1"] = "test_file"

            with open((test_json := os.path.join(tempd, f"test_attrs_{fix_use_id}.json")), "w") as out_f:
                json.dump(TEST_DATA, out_f, indent=2)
            run.save_file(test_json, category="output", name="test_attributes")
            TEST_DATA["file_2"] = "test_attributes"

            with open((test_script := os.path.join(tempd, "test_script.py")), "w") as out_f:
                out_f.write(
                    "print('Hello World!')"
                )
            run.save_file(test_script, category="code", name="test_empty_file")
            TEST_DATA["file_3"] = "test_empty_file"

    time.sleep(1.)
    return TEST_DATA