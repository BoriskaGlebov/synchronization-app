import os
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

CONFIG_PATH_ENV = "SYNC_CONFIG"
DEFAULT_CONFIG_PATH = Path("config/settings.toml")


class SyncSettings(BaseModel):
    """Параметры синхронизации.

    Attributes:
        remote_folder: Папка на Яндекс Диске.
        local_folder: Папка назначения (локальная или сетевой диск).
        interval_seconds: Пауза между циклами синхронизации.
    """

    remote_folder: str = "/"
    local_folder: Path
    interval_seconds: int = Field(default=60, gt=0)


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
        yandex_token: OAuth-токен Яндекс Диска.
        sync: Параметры синхронизации.
        logging: Параметры логирования.
    """

    model_config = SettingsConfigDict(
        env_prefix="SYNC_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    yandex_token: SecretStr
    sync: SyncSettings
    logging: LoggingSettings = LoggingSettings()

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
