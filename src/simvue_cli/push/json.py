import pydantic
import json

from .core import PushAPI
from simvue.api.objects import Folder


class PushJSON(PushAPI):
    @pydantic.validate_call
    def load_from_metadata(
        self, input_file: pydantic.FilePath, *, folder: str
    ) -> str | None:
        with input_file.open() as in_f:
            _data = json.load(in_f)

        _folder = Folder.new(path=folder)
        _folder.commit()

        if not isinstance(_data, list):
            raise ValueError("Expected JSON content to be a list.")

        for json_block in _data:
            self.add_run(metadata=json_block, folder=folder)

        self.push()
        return _folder.id

    @pydantic.validate_call
    def load(self, input_file: pydantic.FilePath, *, folder: str) -> list[str | None]:
        with input_file.open() as in_f:
            _data = json.load(in_f)

        _folder = Folder.new(path=folder)
        _folder.commit()

        _folder_ids: list[str | None] = [_folder.id]

        if not isinstance(_data, list):
            raise ValueError("Expected JSON content to be a list.")

        for json_block in _data:
            if _folder_path := json_block.get("folder"):
                _folder = Folder.new(path=_folder_path)
                _folder.commit()

                _folder_ids.append(_folder.id)
            self.add_run(
                folder=folder or json_block.get("folder"),
                name=json_block.get("name"),
                description=json_block.get("description"),
                metadata=json_block.get("metadata"),
                metrics=json_block.get("metrics"),
            )
        self.push()
        return _folder_ids
