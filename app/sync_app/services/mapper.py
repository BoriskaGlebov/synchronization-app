from dataclasses import dataclass
from pathlib import PurePosixPath

from loguru import logger

from sync_app.core.settings import FolderMapping
from sync_app.models import FileInfo
from sync_app.services.checks import safe_name


@dataclass(frozen=True, slots=True)
class MappedFiles:
    """Файлы Яндекс Диска, разложенные по путям назначения.

    Attributes:
        files: Описания файлов по пути назначения относительно корневой папки.
        sources: Полный путь на Яндекс Диске по пути назначения.
        collisions: Пары (пропущенный файл, занявший место файл) при совпадении путей.
        renamed: Пары (путь на Диске, путь назначения) для файлов с изменённым именем.
    """

    files: dict[str, FileInfo]
    sources: dict[str, str]
    collisions: list[tuple[str, str]]
    renamed: list[tuple[str, str]]


class FolderMapper:
    """Переводит пути файлов Яндекс Диска в пути назначения по списку соответствий.

    Для каждого файла выбирается самое длинное подходящее соответствие. Файлы вне
    всех соответствий пропускаются.

    Args:
        mappings: Список соответствий папок.
        sanitize: Заменять недопустимые для сетевых дисков символы в именах с Диска.

    Raises:
        ValueError: В пути соответствия есть `..`.
    """

    def __init__(self, mappings: list[FolderMapping], sanitize: bool = True) -> None:
        self._sanitize = sanitize
        self._rules = sorted(
            ((self._normalize(m.remote), self._normalize(m.local)) for m in mappings),
            key=lambda rule: len(rule[0]),
            reverse=True,
        )

    @staticmethod
    def _normalize(path: str) -> str:
        parts = tuple(part.strip() for part in PurePosixPath(path.strip("/")).parts)
        if ".." in parts:
            raise ValueError(f"Недопустимый путь в соответствии папок: {path}")
        return "/".join(parts)

    def local_folders(self) -> list[str]:
        """Возвращает подпапки назначения из соответствий, пустая строка означает весь корень."""
        folders = sorted({local for _, local in self._rules}, key=len)
        return [""] if "" in folders else folders

    def remote_folders(self) -> list[str]:
        """Возвращает папки Диска из соответствий, которые нужно просматривать."""
        return ["/" + remote for remote, _ in self._rules]

    def target_of(self, remote_path: str, sanitize: bool | None = None) -> str | None:
        """Возвращает путь назначения для файла Диска или `None`, если он не сопоставлен.

        Args:
            remote_path: Полный путь файла на Диске.
            sanitize: Заменять ли недопустимые символы; по умолчанию как задано в объекте.
        """
        clean = self._sanitize if sanitize is None else sanitize
        relative = remote_path.strip("/")
        for remote, local in self._rules:
            if not remote:
                return f"{local}/{self._clean(relative, clean)}".strip("/")
            if relative.startswith(remote + "/"):
                rest = self._clean(relative.removeprefix(remote + "/"), clean)
                return f"{local}/{rest}".strip("/")
        return None

    @staticmethod
    def _clean(relative: str, sanitize: bool) -> str:
        if not sanitize:
            return relative
        return "/".join(safe_name(part) for part in relative.split("/"))

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
        collisions: list[tuple[str, str]] = []
        renamed: list[tuple[str, str]] = []
        for remote_path, info in sorted(remote.items()):
            target = self.target_of(remote_path)
            if target is None:
                continue
            if target in sources:
                collisions.append((remote_path, sources[target]))
                logger.warning(
                    "{} пропущен: путь {} уже занят {}", remote_path, target, sources[target]
                )
                continue
            if target != self.target_of(remote_path, sanitize=False):
                renamed.append((remote_path, target))
            files[target] = FileInfo(target, info.size, info.modified)
            sources[target] = remote_path
        return MappedFiles(files, sources, collisions, renamed)
