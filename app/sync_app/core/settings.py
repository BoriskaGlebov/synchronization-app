import os
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH_ENV = "SYNC_CONFIG"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.toml"


class FolderMapping(BaseModel):
    """Соответствие папки на Яндекс Диске папке назначения.

    Attributes:
        remote: Папка на Яндекс Диске, `/` означает весь диск.
        local: Подпапка внутри `local_folder`, пустая строка означает сам `local_folder`.
    """

    remote: str
    local: str = ""


class SyncSettings(BaseModel):
    """Параметры синхронизации.

    Attributes:
        local_folder: Корневая папка назначения (локальная или сетевой диск).
        mappings: Какие папки Диска в какие подпапки назначения копировать.
        interval_seconds: Пауза между циклами синхронизации.
        concurrency: Максимум одновременных скачиваний.
    """

    local_folder: Path
    mappings: list[FolderMapping] = Field(default_factory=lambda: [FolderMapping(remote="/")])
    interval_seconds: int = Field(default=60, gt=0)
    concurrency: int = Field(default=5, gt=0)


class AuthSettings(BaseModel):
    """Параметры OAuth (несекретные).

    Attributes:
        redirect_uri: Redirect URI из настроек приложения на oauth.yandex.ru.
        token_file: Файл, где хранятся полученные токены.
    """

    redirect_uri: str | None = None
    token_file: Path = Path("secrets/token.json")


class LoggingSettings(BaseModel):
    """Параметры логирования.

    Attributes:
        dir: Каталог для файлов журнала.
        level_stdout: Уровень вывода в консоль.
        level_file: Уровень основного файла журнала.
        level_error: Уровень файла ошибок.
    """

    dir: Path = Path("logs")
    level_stdout: str = "INFO"
    level_file: str = "INFO"
    level_error: str = "WARNING"


class Settings(BaseSettings):
    """Настройки приложения.

    Несекретные параметры берутся из TOML-файла (путь в `SYNC_CONFIG`,
    по умолчанию `config/settings.toml`), секреты только из окружения или `.env`.

    Attributes:
        yandex_client_id: ClientID приложения Яндекс OAuth.
        yandex_client_secret: Client secret приложения Яндекс OAuth.
        sync: Параметры синхронизации.
        auth: Параметры OAuth.
        logging: Параметры логирования.
    """

    model_config = SettingsConfigDict(
        env_prefix="SYNC_",
        env_nested_delimiter="__",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )

    yandex_client_id: str
    yandex_client_secret: SecretStr
    sync: SyncSettings
    auth: AuthSettings = AuthSettings()
    logging: LoggingSettings = LoggingSettings()

    @model_validator(mode="after")
    def _resolve_relative_paths(self) -> Self:
        """Считает относительные пути от корня проекта, а не от текущей папки."""
        self.auth.token_file = PROJECT_ROOT / self.auth.token_file
        self.logging.dir = PROJECT_ROOT / self.logging.dir
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Задаёт приоритет источников: аргументы, окружение, `.env`, TOML."""
        config_path = Path(os.environ.get(CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH))
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls, toml_file=config_path),
        )
