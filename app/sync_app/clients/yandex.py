import asyncio
import json
from collections.abc import Sequence
from datetime import UTC
from pathlib import Path
from types import TracebackType
from typing import Self

from loguru import logger
from yadisk import AsyncClient
from yadisk.objects import AsyncResourceObject, TokenObject

from sync_app.core.exceptions import AuthRequiredError
from sync_app.core.settings import Settings
from sync_app.models import FileInfo

PAGE_SIZE = 1000
PROGRESS_STEP = 2000
LISTING_CONCURRENCY = 8
DOWNLOAD_TIMEOUT = 30


class TokenStore:
    """Хранит токены OAuth в файле с правами только для владельца.

    Args:
        path: Путь к файлу с токенами.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str] | None:
        """Возвращает сохранённые токены или `None`, если файла нет."""
        if not self.path.exists():
            return None
        data: dict[str, str] = json.loads(self.path.read_text(encoding="utf-8"))
        return data

    def save(self, token: TokenObject) -> None:
        """Сохраняет токены, создавая файл с правами 0600."""
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {"access_token": token.access_token, "refresh_token": token.refresh_token}
        self.path.touch(mode=0o600)
        self.path.write_text(json.dumps(payload), encoding="utf-8")


class YandexDisk:
    """Работа с Яндекс Диском: вход, токен и файловые операции.

    Скрывает библиотеку `yadisk`: остальной код видит только этот класс и `FileInfo`.

    Args:
        client: Асинхронный клиент `yadisk` с заданными id и secret.
        store: Хранилище токенов.
        redirect_uri: Redirect URI приложения для получения кода.
    """

    def __init__(
        self,
        client: AsyncClient,
        store: TokenStore,
        redirect_uri: str | None = None,
    ) -> None:
        self.client = client
        self.store = store
        self.redirect_uri = redirect_uri or None
        self._listing = asyncio.Semaphore(LISTING_CONCURRENCY)

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        """Создаёт объект из настроек приложения."""
        client = AsyncClient(
            id=settings.yandex_client_id,
            secret=settings.yandex_client_secret.get_secret_value(),
            session="httpx",
        )
        return cls(
            client,
            TokenStore(settings.auth.token_file),
            settings.auth.redirect_uri,
        )

    async def __aenter__(self) -> Self:
        """Открывает HTTP-сессию клиента."""
        await self.client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Закрывает HTTP-сессию клиента."""
        await self.client.__aexit__(exc_type, exc, traceback)

    async def authorize(self) -> None:
        """Получает токены по коду подтверждения и сохраняет их."""
        print("Откройте ссылку, разрешите доступ и вставьте код подтверждения:")
        print(self.client.get_code_url(redirect_uri=self.redirect_uri))
        code = input("Код: ").strip()
        self.store.save(await self.client.get_token(code))

    async def ensure_token(self) -> None:
        """Подставляет в клиент действующий токен, при необходимости обновляя его.

        Raises:
            AuthRequiredError: Токенов нет или обновить их не удалось.
        """
        tokens = self.store.load()
        if tokens is None:
            raise AuthRequiredError("Токен не найден, выполните `sync-app auth`")
        self.client.token = tokens["access_token"]
        if await self.client.check_token():
            return
        refresh = tokens.get("refresh_token")
        if not refresh:
            raise AuthRequiredError("Токен истёк, выполните `sync-app auth`")
        token = await self.client.refresh_token(refresh)
        if not token.access_token:
            raise AuthRequiredError("Не удалось обновить токен, выполните `sync-app auth`")
        self.store.save(token)
        self.client.token = token.access_token

    async def walk_files(self, folders: Sequence[str]) -> dict[str, FileInfo]:
        """Возвращает файлы указанных папок диска, включая вложенные.

        Просматриваются только эти папки. Если среди них корень `/`, быстрее прочитать
        плоский список всех файлов диска, это делается одним потоком запросов.

        Args:
            folders: Папки диска вида `/Папка`.

        Returns:
            Словарь, где ключ это полный путь файла на диске вида `/папка/файл.jpg`.
        """
        roots = self._top_level(folders)
        files: dict[str, FileInfo] = {}
        if "/" in roots:
            async for item in self.client.get_files(limit=PAGE_SIZE):
                self._add(files, item)
                if len(files) % PROGRESS_STEP == 0:
                    logger.info("Просмотрено файлов на Диске: {}", len(files))
            return files
        for root in roots:
            logger.info("Просматриваю папку на Диске: {}", root)
            await self._walk_folder(root, files)
        return files

    @staticmethod
    def _top_level(folders: Sequence[str]) -> list[str]:
        """Оставляет только папки, не вложенные в другие из списка."""
        normalized = sorted(
            {"/" + folder.strip("/") for folder in folders}, key=lambda f: (len(f), f)
        )
        roots: list[str] = []
        for folder in normalized:
            if not any(root == "/" or folder.startswith(root + "/") for root in roots):
                roots.append(folder)
        return roots

    async def _walk_folder(self, root: str, files: dict[str, FileInfo]) -> None:
        pending = [root]
        while pending:
            folders = pending
            pending = []
            async with asyncio.TaskGroup() as group:
                results = [group.create_task(self._list_folder(folder)) for folder in folders]
            for task in results:
                for item in task.result():
                    if item.type == "dir" and item.path:
                        pending.append(item.path.removeprefix("disk:"))
                    else:
                        self._add(files, item)
            logger.info("Просмотрено файлов в {}: {}", root, len(files))

    async def _list_folder(self, folder: str) -> list[AsyncResourceObject]:
        async with self._listing:
            return [item async for item in self.client.listdir(folder)]

    @staticmethod
    def _add(files: dict[str, FileInfo], item: AsyncResourceObject) -> None:
        if item.type == "file" and item.path and item.modified:
            path = item.path.removeprefix("disk:")
            modified = item.modified.astimezone(UTC).replace(microsecond=0)
            files[path] = FileInfo(path, item.size or 0, modified)

    async def download(self, remote_path: str, destination: Path) -> None:
        """Скачивает файл с диска.

        Args:
            remote_path: Полный путь файла на диске.
            destination: Куда сохранить файл на локальном диске.
        """
        await self.client.download(remote_path, str(destination), timeout=DOWNLOAD_TIMEOUT)
