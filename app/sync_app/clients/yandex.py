import json
from datetime import UTC
from pathlib import Path
from types import TracebackType
from typing import Self

from yadisk import AsyncClient
from yadisk.objects import TokenObject

from sync_app.core.exceptions import AuthRequiredError
from sync_app.core.settings import Settings
from sync_app.models import FileInfo


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
    """Работа с одной папкой Яндекс Диска: вход, токен и файловые операции.

    Скрывает библиотеку `yadisk`: остальной код видит только этот класс и `FileInfo`.

    Args:
        client: Асинхронный клиент `yadisk` с заданными id и secret.
        store: Хранилище токенов.
        remote_folder: Папка на диске, с которой работает объект.
        redirect_uri: Redirect URI приложения для получения кода.
    """

    def __init__(
        self,
        client: AsyncClient,
        store: TokenStore,
        remote_folder: str,
        redirect_uri: str | None = None,
    ) -> None:
        self.client = client
        self.store = store
        self.remote_folder = "/" + remote_folder.strip("/")
        self.redirect_uri = redirect_uri or None

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
            settings.sync.remote_folder,
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

    async def list_files(self) -> dict[str, FileInfo]:
        """Возвращает файлы папки (без вложенных) по имени."""
        return {
            item.name: FileInfo(
                item.name, item.size or 0, item.modified.astimezone(UTC).replace(microsecond=0)
            )
            async for item in self.client.listdir(self.remote_folder)
            if item.type == "file" and item.name and item.modified
        }

    async def upload(self, local_path: Path, overwrite: bool = False) -> None:
        """Загружает файл в папку под его именем.

        Args:
            local_path: Путь к локальному файлу.
            overwrite: Перезаписать файл, если он уже есть.
        """
        await self.client.upload(
            str(local_path), self._remote_path(local_path.name), overwrite=overwrite
        )

    async def remove(self, name: str) -> None:
        """Перемещает файл папки в корзину."""
        await self.client.remove(self._remote_path(name), permanently=False)

    def _remote_path(self, name: str) -> str:
        return f"{self.remote_folder.rstrip('/')}/{name}"
