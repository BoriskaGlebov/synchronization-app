from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FileInfo:
    """Описание файла в хранилище.

    Attributes:
        name: Имя файла.
        size: Размер в байтах.
        modified: Время последнего изменения в UTC, без микросекунд.
    """

    name: str
    size: int
    modified: datetime
