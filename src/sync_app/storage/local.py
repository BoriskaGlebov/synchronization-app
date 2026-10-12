from datetime import UTC, datetime
from pathlib import Path

from sync_app.core.exceptions import LocalFolderNotFoundError
from sync_app.models import FileInfo


class LocalStorage:
    """Папка на локальном или сетевом диске.

    Args:
        root: Корневая папка синхронизации.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def list_files(self) -> dict[str, FileInfo]:
        """Возвращает файлы папки (без вложенных) по имени.

        Raises:
            LocalFolderNotFoundError: Папки не существует.
        """
        if not self.root.is_dir():
            raise LocalFolderNotFoundError(f"Нет такой папки: {self.root}")
        files: dict[str, FileInfo] = {}
        for entry in self.root.iterdir():
            if entry.is_file():
                stat = entry.stat()
                modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(microsecond=0)
                files[entry.name] = FileInfo(entry.name, stat.st_size, modified)
        return files

    def path_of(self, name: str) -> Path:
        """Возвращает полный путь к файлу по имени."""
        return self.root / name
