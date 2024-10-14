import random
import string
from _pytest.compat import LEGACY_PATH
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
        assert result.exit_code == 0

        config = toml.load(SIMVUE_CONFIG_FILENAME)

        assert config["server"].get(
            component
        ) == (TEST_SERVER if component == "url" else TEST_TOKEN)


@pytest.mark.parametrize(
    "tab_format", tabulate._table_formats.keys()
)
def test_runs_list(create_plain_run: tuple[simvue.Run, dict], tab_format: str) -> None:
    run, _ = create_plain_run
    runner = click.testing.CliRunner()
    result = runner.invoke(
        sv_cli.simvue,
        [
            "run",
            "list",
            f"--format={tab_format}"
        ]
    )
    assert result.exit_code == 0
    assert run.id and run.id in result.output


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
    assert result.exit_code == 0
    json_data = json.loads(result.output)
    assert json_data.get("tags") == run_data["tags"]


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
    assert result.exit_code == 0
    if state == "create":
        return
    time.sleep(1.0)
    client = simvue.Client()
    assert client.get_run((run_id := result.output.strip()))
    result = runner.invoke(
        sv_cli.simvue,
        [
            "run",
            "close" if state != "abort" else "abort",
            run_id
        ]
    )
    assert result.exit_code == 0
    time.sleep(1)
    run_data = client.get_run(run_id)
    assert run_data["status"] == "terminated" if state == "abort" else "completed"


@pytest.mark.parametrize(
    "tab_format", tabulate._table_formats.keys()
)
def test_folder_list(create_plain_run: tuple[simvue.Run, dict], tab_format: str) -> None:
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
            f"--format={tab_format}"
        ]
    )
    assert result.exit_code == 0
    assert run_data["folder"] in result.output


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
        click_script = pathlib.Path(__file__).parents[1].joinpath("simvue_cli", "cli", "__init__.py")
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
                assert command_2.returncode == 0
    time.sleep(1.0)
    client = simvue.Client()
    run_data = client.get_runs(filters=["has tag.test_simvue_monitor"])
    assert run_data
    assert client.get_metric_values(run_ids=[run_data[0]["id"]], metric_names=["x", "y"], xaxis="step")
