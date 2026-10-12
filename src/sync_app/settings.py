from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, читаются из переменных окружения.

    Attributes:
        yandex_token: OAuth-токен Яндекс Диска.
        remote_folder: Папка на Яндекс Диске, которую зеркалим.
        local_folder: Папка назначения (локальная или сетевой диск).
        interval_minutes: Интервал между синхронизациями в режиме демона.
        log_path: Каталог для файлов журнала.
    """

    model_config = SettingsConfigDict(env_prefix="SYNC_", env_file=".env", extra="ignore")

    yandex_token: SecretStr
    remote_folder: str = "/"
    local_folder: Path
    interval_minutes: int = 60
    log_path: Path = Path("logs")
