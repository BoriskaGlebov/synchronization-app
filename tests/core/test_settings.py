from pathlib import Path

import pytest
from pydantic import ValidationError

from sync_app.core.settings import Settings


def test_reads_toml_and_secret_from_env(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_YANDEX_TOKEN", "secret")

    settings = Settings()

    assert settings.yandex_token.get_secret_value() == "secret"
    assert settings.sync.remote_folder == "/Фото"
    assert settings.sync.local_folder == Path("/mnt/nas")
    assert settings.sync.interval_seconds == 15
    assert settings.logging.level_stdout == "DEBUG"
    assert settings.logging.level_error == "WARNING"


def test_env_overrides_toml(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_YANDEX_TOKEN", "secret")
    monkeypatch.setenv("SYNC_SYNC__INTERVAL_SECONDS", "5")

    assert Settings().sync.interval_seconds == 5


def test_token_is_hidden_in_repr(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_YANDEX_TOKEN", "secret")

    assert "secret" not in repr(Settings())


def test_requires_token(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNC_YANDEX_TOKEN", raising=False)

    with pytest.raises(ValidationError):
        Settings()
