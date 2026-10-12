import json
from datetime import UTC
from pathlib import Path

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


def build_client(settings: Settings) -> AsyncClient:
    """Создаёт асинхронный клиент Яндекс Диска на httpx."""
    return AsyncClient(
        id=settings.yandex_client_id,
        secret=settings.yandex_client_secret.get_secret_value(),
        session="httpx",
    )


async def authorize(client: AsyncClient, store: TokenStore, redirect_uri: str | None) -> None:
    """Получает токены по коду подтверждения и сохраняет их.

    Args:
        client: Клиент с заданными id и secret.
        store: Хранилище токенов.
        redirect_uri: Redirect URI приложения.
    """
    print("Откройте ссылку, разрешите доступ и вставьте код подтверждения:")
    print(client.get_code_url(redirect_uri=redirect_uri or None))
    code = input("Код: ").strip()
    store.save(await client.get_token(code))


async def ensure_token(client: AsyncClient, store: TokenStore) -> None:
    """Подставляет в клиент действующий токен, при необходимости обновляя его.

    Raises:
        AuthRequiredError: Токенов нет или обновить их не удалось.
    """
    tokens = store.load()
    if tokens is None:
        raise AuthRequiredError("Токен не найден, выполните `sync-app auth`")
    client.token = tokens["access_token"]
    if await client.check_token():
        return
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise AuthRequiredError("Токен истёк, выполните `sync-app auth`")
    token = await client.refresh_token(refresh)
    if not token.access_token:
        raise AuthRequiredError("Не удалось обновить токен, выполните `sync-app auth`")
    store.save(token)
    client.token = token.access_token


async def list_files(client: AsyncClient, folder: str) -> dict[str, FileInfo]:
    """Возвращает файлы папки Яндекс Диска (без вложенных) по имени."""
    return {
        item.name: FileInfo(
            item.name, item.size or 0, item.modified.astimezone(UTC).replace(microsecond=0)
        )
        async for item in client.listdir(folder)
        if item.type == "file" and item.name and item.modified
    }
