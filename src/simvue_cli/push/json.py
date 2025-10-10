import pydantic
import json

from .validate import JsonRunUpload, MetadataUpload

from .core import PushAPI
from simvue.api.objects import Folder


class PushJSON(PushAPI):
    @pydantic.validate_call
    def load_from_metadata(
        self,
        input_file: pydantic.FilePath,
        *,
        folder: str | None = None,
        name: str | None = None,
    ) -> str | None:
        with input_file.open() as in_f:
            _data = MetadataUpload(metadata=json.load(in_f))

        _folder_name = folder or "/"
        _folder = Folder.new(path=_folder_name)
        _folder.commit()

        for i, json_block in enumerate(_data.metadata):
            self.add_run(
                name=f"{name}-{i}" if name else None, metadata=json_block, folder=folder
            )

        self.push()
        return _folder.id

    @pydantic.validate_call
    def load(
        self,
        input_file: pydantic.FilePath,
        *,
        folder: str | None = None,
        name: str | None = None,
    ) -> list[str | None]:
        with input_file.open() as in_f:
            _data = JsonRunUpload(**json.load(in_f))

        _folder_name = folder or _data.folder
        _folder_name = _folder_name or "/"
        _folder = Folder.new(path=_folder_name)
        _folder.commit()

        _folder_ids: list[str | None] = [_folder.id]

        for i, _run in enumerate(_data.runs):
            if _folder_path := _run.folder:
                _folder_name = f"{_folder_name}{_folder_path}"
                _folder_name = _folder_name.replace("//", "/")
                _folder = Folder.new(path=_folder_name)
                _folder.commit()

                _folder_ids.append(_folder.id)
            self.add_run(
                folder=_folder_name,
                name=f"{name}-{i}" if name else None or _run.name,
                description=_run.description,
                metadata=_run.metadata,
                metrics=_run.metrics,
            )
        self.push()
        return _folder_ids
