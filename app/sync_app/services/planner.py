from dataclasses import dataclass

from sync_app.models import FileInfo


@dataclass(frozen=True, slots=True)
class Download:
    """Файл, который нужно скачать.

    Attributes:
        path: Путь относительно папки синхронизации.
        remote: Описание файла на Яндекс Диске.
    """

    path: str
    remote: FileInfo


def plan_downloads(remote: dict[str, FileInfo], local: dict[str, FileInfo]) -> list[Download]:
    """Определяет, что скачать, чтобы локальная папка содержала всё из Яндекс Диска.

    Файл скачивается, если его нет локально или размер отличается. Ничего не удаляется.

    Args:
        remote: Файлы на Яндекс Диске.
        local: Файлы в локальной папке.

    Returns:
        Список загрузок, отсортированный по пути.
    """
    return [
        Download(path, info)
        for path, info in sorted(remote.items())
        if path not in local or local[path].size != info.size
    ]
