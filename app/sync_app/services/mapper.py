from dataclasses import dataclass
from pathlib import PurePosixPath

from loguru import logger

from sync_app.core.settings import FolderMapping
from sync_app.models import FileInfo


@dataclass(frozen=True, slots=True)
class MappedFiles:
    """Файлы Яндекс Диска, разложенные по путям назначения.

    Attributes:
        files: Описания файлов по пути назначения относительно корневой папки.
        sources: Полный путь на Яндекс Диске по пути назначения.
    """

    files: dict[str, FileInfo]
    sources: dict[str, str]


class FolderMapper:
    """Переводит пути файлов Яндекс Диска в пути назначения по списку соответствий.

    Для каждого файла выбирается самое длинное подходящее соответствие. Файлы вне
    всех соответствий пропускаются.

    Args:
        mappings: Список соответствий папок.

    Raises:
        ValueError: В пути соответствия есть `..`.
    """

    def __init__(self, mappings: list[FolderMapping]) -> None:
        self._rules = sorted(
            ((self._normalize(m.remote), self._normalize(m.local)) for m in mappings),
            key=lambda rule: len(rule[0]),
            reverse=True,
        )

    @staticmethod
    def _normalize(path: str) -> str:
        parts = PurePosixPath(path.strip("/")).parts
        if ".." in parts:
            raise ValueError(f"Недопустимый путь в соответствии папок: {path}")
        return "/".join(parts)

    def target_of(self, remote_path: str) -> str | None:
        """Возвращает путь назначения для файла Диска или `None`, если он не сопоставлен."""
        relative = remote_path.strip("/")
        for remote, local in self._rules:
            if not remote:
                return f"{local}/{relative}".strip("/")
            if relative.startswith(remote + "/"):
                return f"{local}/{relative.removeprefix(remote + '/')}".strip("/")
        return None

    def map_files(self, remote: dict[str, FileInfo]) -> MappedFiles:
        """Раскладывает файлы Диска по путям назначения.

        Args:
            remote: Файлы Диска по полному пути.

        Returns:
            Файлы по пути назначения и их исходные пути. Если два файла претендуют
            на один путь назначения, берётся первый, о втором пишется предупреждение.
        """
        files: dict[str, FileInfo] = {}
        sources: dict[str, str] = {}
        for remote_path, info in sorted(remote.items()):
            target = self.target_of(remote_path)
            if target is None:
                continue
            if target in sources:
                logger.warning(
                    "{} пропущен: путь {} уже занят {}", remote_path, target, sources[target]
                )
                continue
            files[target] = FileInfo(target, info.size, info.modified)
            sources[target] = remote_path
        return MappedFiles(files, sources)
