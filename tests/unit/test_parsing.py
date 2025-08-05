import pytest
import pathlib
import typing
import simvue_cli.session.config.parsing.csv as svp

@pytest.mark.parametrize(
    "method", ("tail", "track")
)
def test_parse_csv(method: typing.Literal["tail", "track"]) -> None:
    _data_file = pathlib.Path(__file__).parents[1].joinpath("data", "sample_users.csv")
    with _data_file.open() as in_f:
        if method == "tail":
            _reduced_content = "\n".join(in_f.read().split("\n")[10:20])
            _, _out = svp.CSV(header_line_index=1)._parse_log(file_content=_reduced_content)
        else:
            _, _out = svp.CSV(header_line_index=1)._parse_file(input_file=f"{_data_file}")
        assert _out