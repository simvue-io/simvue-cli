import pathlib
from simvue_cli.session.workflow import Workflow
from simvue_cli.session.config.schema import Status

def test_example_non_simvue_workflow() -> None:
    _example_file = pathlib.Path(__file__).parent.joinpath("data", "nosimvue_session.yml")
    for step in Workflow.from_file(_example_file).play():
        assert step.status == Status.Waiting, f"Expected 'waiting' got '{step.status}' for '{step.label}'"
        assert step._return_code == 0

def test_example_simvue_workflow() -> None:
    pass
