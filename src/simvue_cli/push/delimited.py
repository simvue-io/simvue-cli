import pydantic
import csv
from .core import PushAPI
from simvue.api.objects import Folder


class PushDelimited(PushAPI):
    @pydantic.validate_call
    def load_from_metadata(
        self, input_file: pydantic.FilePath, *, folder: str, delimiter: str = ","
    ) -> str | None:
        _folder = Folder.new(path=folder)
        _folder.commit()
        with input_file.open(newline="") as in_f:
            for row in csv.DictReader(in_f, delimiter=delimiter):
                self.add_run(metadata=row, folder=folder)
        self.push()
        return _folder.id

    def load(self, *_, **__) -> None:
        raise NotImplementedError
