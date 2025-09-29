import pydantic
import json

from .core import PushAPI
from simvue.api.objects import Folder


class PushJSON(PushAPI):
    @pydantic.validate_call
    def load_from_metadata(
        self, input_file: pydantic.FilePath, *, folder: str, name: str | None = None,
    ) -> str | None:
        with input_file.open() as in_f:
            _data = json.load(in_f)

        _folder = Folder.new(path=folder)
        _folder.commit()

        if not isinstance(_data, list):
            raise ValueError("Expected JSON content to be a list.")

        for i, json_block in enumerate(_data):
            self.add_run(name=f"{name}-{i}" if name else None, metadata=json_block, folder=folder)

        self.push()
        return _folder.id

    @pydantic.validate_call
    def load(self, input_file: pydantic.FilePath, *, folder: str, name: str | None = None) -> list[str | None]:
        with input_file.open() as in_f:
            _data = json.load(in_f)

        _folder = Folder.new(path=folder)
        _folder.commit()

        _folder_ids: list[str | None] = [_folder.id]

        if not isinstance(_data, list):
            raise ValueError("Expected JSON content to be a list.")

        for i, json_block in enumerate(_data):
            if _folder_path := json_block.get("folder"):
                _folder = Folder.new(path=_folder_path)
                _folder.commit()

                _folder_ids.append(_folder.id)
            self.add_run(
                folder=folder or json_block.get("folder"),
                name=f"{name}-{i}" if name else None or json_block.get("name"),
                description=json_block.get("description"),
                metadata=json_block.get("metadata"),
                metrics=json_block.get("metrics"),
            )
        self.push()
        return _folder_ids
