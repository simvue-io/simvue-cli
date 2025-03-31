import json
import typing
import pydantic
import simvue.api.objects as sv_obj
from simvue.models import FOLDER_REGEX


def hierarchy(path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)]) -> str:
    _hierarchical_structure = {}
    for _, folder in sv_obj.Folder.get(
        filters=json.dumps([f"path contains {path}"]),
        sorting=[{"column": "created", "descending": True}],
    ):
        _components = folder.path.strip("/").split("/")
        _node = _hierarchical_structure
        for i, _component in enumerate(_components):
            if _component not in _node:
                _node[_component] = {}
            _node = _node[_component]

    for entry
    return _hierarchical_structure


if __name__ in "__main__":
    print(hierarchy("/simvue_unit_tests"))
