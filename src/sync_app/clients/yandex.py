from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from sync_app.core.exceptions import RemoteFolderNotFoundError, YandexAuthError
from sync_app.models import FileInfo

API_URL = "https://cloud-api.yandex.net/v1/disk"
PAGE_SIZE = 1000
LIST_FIELDS = (
    "_embedded.total,_embedded.items.name,_embedded.items.type,"
    "_embedded.items.size,_embedded.items.modified"
)


class YandexDiskClient:
    """Клиент REST API Яндекс Диска для одной удалённой папки.

    Args:
        token: OAuth-токен.
        remote_folder: Папка на диске, с которой работает клиент.
        session: HTTP-сессия, по умолчанию создаётся новая.
        timeout: Таймаут запросов в секундах.
    """

    def __init__(
        self,
        token: str,
        remote_folder: str,
        session: requests.Session | None = None,
        timeout: float = 30,
    ) -> None:
        self.remote_folder = "/" + remote_folder.strip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "Authorization": f"OAuth {token}"}
        )

    def list_files(self) -> dict[str, FileInfo]:
        """Возвращает файлы удалённой папки (без вложенных) по имени.

        Raises:
            YandexAuthError: Токен отклонён.
            RemoteFolderNotFoundError: Папки нет на диске.
        """
        files: dict[str, FileInfo] = {}
        offset = 0
        while True:
            embedded = self._get(
                "/resources",
                path=self.remote_folder,
                fields=LIST_FIELDS,
                limit=PAGE_SIZE,
                offset=offset,
            )["_embedded"]
            for item in embedded["items"]:
                if item["type"] == "file":
                    files[item["name"]] = self._to_file_info(item)
            offset += PAGE_SIZE
            if offset >= embedded["total"]:
                return files

    def upload(self, local_path: Path, overwrite: bool = False) -> None:
        """Загружает файл в удалённую папку под его именем.

        Args:
            local_path: Путь к локальному файлу.
            overwrite: Перезаписать файл, если он уже есть.
        """
        href = self._get(
            "/resources/upload", path=self._remote_path(local_path.name), overwrite=overwrite
        )["href"]
        with local_path.open("rb") as file:
            response = self.session.put(href, data=file, timeout=self.timeout)
        response.raise_for_status()

    def delete(self, name: str) -> None:
        """Удаляет файл из удалённой папки."""
        response = self.session.delete(
            f"{API_URL}/resources",
            params={"path": self._remote_path(name)},
            timeout=self.timeout,
        )
        self._check(response)

    def _remote_path(self, name: str) -> str:
        return f"{self.remote_folder.rstrip('/')}/{name}"

    def _get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        response = self.session.get(f"{API_URL}{endpoint}", params=params, timeout=self.timeout)
        self._check(response)
        result: dict[str, Any] = response.json()
        return result

    @staticmethod
    def _check(response: requests.Response) -> None:
        if response.status_code == 401:
            raise YandexAuthError("Токен Яндекс Диска отклонён")
        if response.status_code == 404:
            raise RemoteFolderNotFoundError("Путь не найден на Яндекс Диске")
        response.raise_for_status()

    @staticmethod
    def _to_file_info(item: dict[str, Any]) -> FileInfo:
        modified = datetime.fromisoformat(item["modified"]).astimezone(UTC)
        return FileInfo(
            name=item["name"], size=item["size"], modified=modified.replace(microsecond=0)
        )
