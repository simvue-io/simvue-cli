import pydantic
import csv
from .core import PushAPI
from simvue.api.objects import Folder
from .validate import MetadataUpload


class PushDelimited(PushAPI):
    @pydantic.validate_call
    def load_from_metadata(
        self,
        input_file: pydantic.FilePath,
        *,
        folder: str | None = None,
        delimiter: str = ",",
        name: str | None = None,
    ) -> str | None:
        _folder_name = folder or "/"
        _folder = Folder.new(path=_folder_name)
        _folder.commit()
        with input_file.open(newline="") as in_f:
            for i, row in enumerate(csv.DictReader(in_f, delimiter=delimiter)):
                _metadata_upload = MetadataUpload(metadata=[row])
                self.add_run(
                    metadata=_metadata_upload.metadata[0],
                    folder=folder,
                    name=f"{name}-{i}" if name else None,
                )
        self.push()
        return _folder.id

    def load(self, *_, **__) -> None:
        raise NotImplementedError
