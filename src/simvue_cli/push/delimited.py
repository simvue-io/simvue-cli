import pydantic
import csv
from .core import PushAPI
from simvue.api.objects import Folder
from .validate import JsonMetadataUpload


class PushDelimited(PushAPI):
    @pydantic.validate_call
    def load_from_metadata(
        self,
        input_file: pydantic.FilePath,
        *,
        folder: str,
        delimiter: str = ",",
        name: str | None = None,
    ) -> str | None:
        _folder = Folder.new(path=folder)
        _folder.commit()
        with input_file.open(newline="") as in_f:
            _metadata_entries = JsonMetadataUpload(
                metadata=list(csv.DictReader(in_f, delimiter=delimiter))
            )
            for i, row in enumerate(_metadata_entries.metadata):
                self.add_run(
                    metadata=row, folder=folder, name=f"{name}-{i}" if name else None
                )
        self.push()
        return _folder.id

    def load(self, *_, **__) -> None:
        raise NotImplementedError
