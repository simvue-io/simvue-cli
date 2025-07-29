import pathlib
from simvue_cli.session.workflow import Workflow

def test_example_non_simvue_workflow() -> None:
    _example_file = pathlib.Path(__file__).parent.joinpath("data", "session.yml")
    for _ in Workflow.from_file(_example_file).play():
        pass
