import random
import string
from uuid import uuid4
from _pytest.compat import LEGACY_PATH
from simvue.api.objects import Alert, Storage, Tenant, User
from simvue.client import ObjectNotFoundError
from simvue.run import RunObject
import tabulate
import simvue
import time
import tempfile
import pathlib

import click.testing
import pytest
import toml
import json
import subprocess

import simvue_cli.cli as sv_cli
from simvue_cli.config import SIMVUE_CONFIG_FILENAME


@pytest.mark.parametrize(
    "component", ("url", "token")
)
def test_config_update(component: str, tmpdir: LEGACY_PATH) -> None:
    with tmpdir.as_cwd():
        TEST_SERVER: str = "https://not-a-simvue.io"
        TEST_TOKEN: str = "".join(random.choice(string.ascii_letters) for _ in range(100))
        runner = click.testing.CliRunner()
        result = runner.invoke(
            sv_cli.simvue,
            [
                "config",
                "server.url" if component == "url" else "server.token",
                TEST_SERVER if component == "url" else TEST_TOKEN
            ]
        )
        assert result.exit_code == 0, result.output

        config = toml.load(SIMVUE_CONFIG_FILENAME)

        assert config["server"].get(
            component
        ) == (TEST_SERVER if component == "url" else TEST_TOKEN)


def test_runs_list(create_plain_run: tuple[simvue.Run, dict]) -> None:
    run, _ = create_plain_run
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "run",
            "list",
            "--format=simple"
        ]
    )
    assert result.exit_code == 0, result.output
    assert run.id and run.id in result.output.replace("\\\\", "\\")


def test_runs_json(create_test_run: tuple[simvue.Run, dict]) -> None:
    run, run_data = create_test_run
    assert run.id
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "run",
            "json",
            run.id
        ]
    )
    assert result.exit_code == 0, result.output
    json_data = json.loads(result.output.replace("'", '"'))
    assert isinstance(json_data, dict), f"Expected dictionary got '{result.output}'"
    assert sorted(json_data.get("tags")) == sorted(run_data["tags"])


@pytest.mark.parametrize(
    "state", ("close", "abort", "create")
)
def test_run_creation(state: str) -> None:
    runner = click.testing.CliRunner()
    cmd = [
        "run",
        "create",
        "--tag=simvue_cli_testing",
        "--tag=test_run_creation",
        "--folder=/simvue_cli_testing",
        "--retention=15",
        f"--name=test_run_creation_{state}"
    ]
    if state == "create":
        cmd.append("--create-only")
    result = runner.invoke(
        sv_cli.simvue,
        cmd
    )
    assert result.exit_code == 0, result.output
    if state == "create":
        return
    time.sleep(1.0)
    client = simvue.Client()
    assert client.get_run((run_id := result.output.strip()))
    result = runner.invoke(
        sv_cli.simvue,
        [
            "run",
            "metadata",
            run_id,
            '{"x": "a value"}'
        ]
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        sv_cli.simvue,
        [
            "run",
            "close" if state != "abort" else "abort",
            run_id
        ]
    )
    assert result.exit_code == 0, result.output
    time.sleep(2)
    run_data = client.get_run(run_id)
    assert run_data.status == ("terminated" if state == "abort" else "completed")
    result = runner.invoke(
        sv_cli.simvue,
        [
            "run",
            "remove",
            run_id
        ]
    )
    assert result.exit_code == 0, result.stdout
    with pytest.raises(ObjectNotFoundError):
        RunObject(identifier=run_id)


@pytest.mark.parametrize(
    "existing_run", (False, True), ids=("new", "existing")
)
def test_log_metrics(create_plain_run: tuple[simvue.Run, dict], existing_run: bool) -> None:
    run, run_data = create_plain_run
    assert run.id
    if existing_run:
        run.log_metrics({"x": -1, "y": (-1)*(-1) + 2*(-1) - 3})
    runner = click.testing.CliRunner()

    for i in range(10):
        time.sleep(0.5)
        x = i - 5
        metrics = json.dumps({"x": x, "y": x*x + 2*x - 3})
        result = runner.invoke(
            sv_cli.simvue,
            [
                "run",
                "log.metrics",
                run.id,
                f"{metrics}"
            ]
        )
        assert result.exit_code == 0, result.output
    time.sleep(2.0)
    client = simvue.Client()
    assert (results := client.get_metric_values(run_ids=[run.id], xaxis="step", metric_names=["x", "y"]))
    assert len(results["x"]) == 10
    assert len(results["y"]) == 10


def test_log_events(create_plain_run: tuple[simvue.Run, dict]) -> None:
    run, run_data = create_plain_run
    assert run.id
    runner = click.testing.CliRunner()

    for i in range(5):
        time.sleep(0.5)
        x = i - 5
        y = x*x + 2*x - 3
        result = runner.invoke(
            sv_cli.simvue,
            [
                "run",
                "log.event",
                run.id,
                f"Event: x={x}, y={y}"
            ]
        )
        assert result.exit_code == 0, result.output
    time.sleep(2.0)
    client = simvue.Client()
    assert (results := client.get_events(run.id))
    assert len(results) == 5


def test_alert_list(create_test_run: tuple[simvue.Run, dict]) -> None:
    _, run_data = create_test_run
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "alert",
            "list",
            "--source",
            "--name",
            "--auto",
            "--run-tags",
            "--enabled",
            "--format=simple",
            "--count=100"
        ]
    )
    assert result.exit_code == 0, result.output
    assert "alert_0" in result.output


def test_user_alert() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "alert",
            "create",
            "test/test_user_alert"
        ]
    )
    _alert = result.output.strip()
    assert result.exit_code == 0, result.output
    time.sleep(1.0)
    result = runner.invoke(
        sv_cli.simvue,
        [
            "alert",
            "json",
            _alert,
        ]
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        sv_cli.simvue,
        [
            "alert",
            "remove",
            _alert
        ]
    )
    assert result.exit_code == 0, result.output
    with pytest.raises(ObjectNotFoundError):
        Alert(identifier=_alert)


def test_server_ping() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "ping",
            "--timeout=5"
        ]
    )
    assert result.exit_code == 0, result.output


def test_about() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "about"
        ]
    )
    assert result.exit_code == 0, result.output

def test_folder_list(create_plain_run: tuple[simvue.Run, dict]) -> None:
    run, run_data = create_plain_run
    assert run.id
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "folder",
            "list",
            "--path",
            "--name",
            "--description",
            "--tags",
            "--enumerate",
            f"--format=simple"
        ]
    )
    assert result.exit_code == 0, result.output
    assert run_data["folder"] in result.output


def test_tag_list(create_plain_run: tuple[simvue.Run, dict]) -> None:
    run, run_data = create_plain_run
    assert run.id
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "tag",
            "list",
            "--name",
            "--created",
            "--color",
            "--enumerate",
            f"--format=simple"
        ]
    )
    assert result.exit_code == 0, result.output
    for tag in run_data["tags"]:
        assert tag in result.output


def test_artifact_list(create_test_run: tuple[simvue.Run, dict]) -> None:
    run, run_data = create_test_run
    assert run.id
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "artifact",
            "list",
            "--name",
            "--original-path",
            "--user",
            "--created",
            "--download-url",
            "--uploaded",
            "--checksum",
            "--size",
            "--storage",
            "--mime-type",
            "--count=20",
            "--enumerate",
            f"--format=simple"
        ]
    )
    assert result.exit_code == 0, result.output
    assert run_data["file_1"] in result.output
    assert run_data["file_2"] in result.output
    assert run_data["file_3"] in result.output


def test_tenant_list() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "tenant",
            "list",
            "--max-runs",
            "--max-data-volume",
            "--max-request-rate",
            "--created",
            "--name",
            "--enabled",
            "--count=20",
            "--enumerate",
            f"--format=simple"
        ]
    )
    assert result.exit_code == 0, result.output


def test_user_list() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "user",
            "list",
            "--username",
            "--email",
            "--full-name",
            "--manager",
            "--admin",
            "--enabled",
            "--read-only",
            "--deleted",
            "--count=20",
            "--enumerate",
            f"--format=simple"
        ]
    )
    assert result.exit_code == 0, result.output


@pytest.mark.unix
def test_add_remove_storage() -> None:
    name = "simvue_cli_test_storage"
    runner = click.testing.CliRunner()
    endpoint_url="https://not-a-real-url.io"
    region_name="fictionsville"
    access_key_id="dummy_key"
    secret_access_key="not_a_key"
    bucket="dummy_bucket"
    is_enabled=False

    with tempfile.NamedTemporaryFile() as temp_f:
        with open(temp_f.name, "w") as out_f:
            out_f.write("not_a_key")

        result = runner.invoke(
            sv_cli.simvue,
            [
                "storage",
                "add",
                "s3",
                name,
                "--endpoint-url",
                endpoint_url,
                "--disable-check",
                "--block-tenant",
                "--access-key-id",
                access_key_id,
                "--bucket",
                bucket,
                "--disable",
                "--region-name",
                region_name,
                "--access-key-file",
                temp_f.name
            ],
            catch_exceptions=False
        )
    assert result.exit_code == 0, result.output
    storage_id = result.stdout.strip()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "storage",
            "remove",
            storage_id
        ]
    )
    assert result.exit_code == 0, result.output
    with pytest.raises(ObjectNotFoundError):
        Storage(identifier=storage_id)


def test_storage() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "storage",
            "list",
            "--name",
            "--backend",
            "--created",
            "--default",
            "--tenant-usable",
            "--enabled",
            "--count=20",
        ],
    )
    assert result.exit_code == 0, result.output
    _storage_id: str = result.stdout.split()[0]
    result = runner.invoke(
        sv_cli.simvue,
        [
            "storage",
            "json",
            _storage_id.strip()
        ],
        catch_exceptions=False
    )
    assert result.exit_code == 0, result.output


def test_user_and_tenant() -> None:
    runner = click.testing.CliRunner()
    _tenant_name = "simvue_cli_tenant"
    _user_name = "jbloggs"
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "tenant",
            "add",
            "--max-request-rate=1",
            "--max-runs=1",
            "--max-data-volume=1",
            _tenant_name
        ]
    )
    _tenant_id = result.stdout.strip()
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "user",
            "add",
            "--full-name",
            "Joe Bloggs",
            "--email",
            "jbloggs@simvue.io",
            "--tenant",
            _tenant_id,
            _user_name
        ],
    )
    _user_id = result.stdout.strip()
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "user",
            "json",
            _user_id
        ]
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "user",
            "remove",
            _user_id
        ]
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "tenant",
            "json",
            _tenant_id
        ]
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        sv_cli.simvue,
        [
            "admin",
            "tenant",
            "remove",
            _tenant_id
        ]
    )
    assert result.exit_code == 0, result.output
    with pytest.raises(ObjectNotFoundError):
        User(identifier=_user_id)
    with pytest.raises(ObjectNotFoundError):
        Tenant(identifier=_tenant_id)


@pytest.mark.unix
def test_simvue_monitor() -> None:
    with tempfile.NamedTemporaryFile(suffix=".sh") as out_f:
        with open(out_f.name, "w", encoding="utf-8") as f_write:
            f_write.write(
                """# Firstly echo headers
echo -e "x\ty"

# Now the data
for i in {1..10}; do
  echo -e "$i\t$((i * 2))"
  sleep 1
done
                """
            )
        click_script = pathlib.Path(__file__).parents[1].joinpath("src", "simvue_cli", "cli", "__init__.py")
        with subprocess.Popen(
            ["bash", out_f.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        ) as command_1:

            with subprocess.Popen(
                [
                    "python",
                    click_script,
                    "monitor",
                    "--name=test_simvue_monitor",
                    "--tag=test_simvue_monitor",
                    "--tag=simvue_cli_tests",
                    "--folder=/simvue_cli_tests",
                    "--retention=15"
                ],
                stdin=command_1.stdout,
                text=True
            ) as command_2:

                command_1.stdout.close()
                command_2.communicate()
                assert command_2.returncode == 0, command_2.stdout
    time.sleep(1.0)
    client = simvue.Client()
    _, run_data = next(client.get_runs(filters=["has tag.test_simvue_monitor"]))
    assert run_data
    assert client.get_metric_values(run_ids=[run_data.id], metric_names=["x", "y"], xaxis="step")


def test_whoami() -> None:
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "whoami"
        ]
    )
    assert result.exit_code == 0, result.stdout


def test_purge(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        monkeypatch.setattr(pathlib.Path, "home", lambda *_, **__: pathlib.Path(tempd))

        # Sanity check
        assert pathlib.Path.home() == (_test_dir := pathlib.Path(tempd))

        _test_dir.joinpath(".simvue").mkdir()
        _test_dir.joinpath(".simvue", "test_json.json").touch()
        _test_dir.joinpath(".simvue.toml").touch()

        runner = click.testing.CliRunner()
        result = runner.invoke(
            sv_cli.simvue,
            [
                "purge"
            ]
        )
        assert result.exit_code == 0, result.stdout
        assert f"{_test_dir.joinpath('.simvue')}" in result.stdout
        assert f"{_test_dir.joinpath('.simvue.toml')}" in result.stdout
        assert not _test_dir.joinpath(".simvue").exists()
        assert not _test_dir.joinpath(".simvue.toml").exists()
