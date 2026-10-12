from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sync_app.core.exceptions import LocalFolderNotFoundError
from sync_app.models import FileInfo

PART_SUFFIX = ".part"


class LocalStorage:
    """Папка на локальном или сетевом диске.

    Args:
        root: Корневая папка синхронизации, должна существовать (смонтирована).
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def list_files(self, subfolders: Iterable[str] = ("",)) -> dict[str, FileInfo]:
        """Возвращает файлы папки, включая вложенные, без недокачанных `.part`.

        Args:
            subfolders: Подпапки корня, которые нужно просмотреть; пустая строка означает
                весь корень. Несуществующие подпапки пропускаются.

        Returns:
            Словарь, где ключ это путь относительно корня с разделителем `/`.

        Raises:
            LocalFolderNotFoundError: Корневой папки не существует.
        """
        if not self.root.is_dir():
            raise LocalFolderNotFoundError(f"Нет такой папки: {self.root}")
        files: dict[str, FileInfo] = {}
        for subfolder in subfolders:
            for entry in (self.root / subfolder).rglob("*"):
                if entry.is_file() and entry.suffix != PART_SUFFIX:
                    stat = entry.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(microsecond=0)
                    relative = entry.relative_to(self.root).as_posix()
                    files[relative] = FileInfo(relative, stat.st_size, modified)
        return files

    def path_of(self, relative_path: str) -> Path:
        """Возвращает полный путь к файлу по относительному.

        Raises:
            ValueError: Путь выходит за пределы корневой папки.
        """
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Путь выходит за пределы папки назначения: {relative_path}")
        return self.root / relative_path
