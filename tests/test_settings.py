from pathlib import Path

import pytest
from pydantic import ValidationError

from sync_app.settings import Settings


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNC_YANDEX_TOKEN", "secret")
    monkeypatch.setenv("SYNC_LOCAL_FOLDER", "/mnt/nas/photos")
    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "15")

    settings = Settings()

    assert settings.yandex_token.get_secret_value() == "secret"
    assert settings.local_folder == Path("/mnt/nas/photos")
    assert settings.interval_minutes == 15
    assert settings.remote_folder == "/"


def test_token_is_hidden_in_repr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNC_YANDEX_TOKEN", "secret")
    monkeypatch.setenv("SYNC_LOCAL_FOLDER", "/tmp")

    assert "secret" not in repr(Settings())


def test_requires_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYNC_YANDEX_TOKEN", raising=False)
    monkeypatch.setenv("SYNC_LOCAL_FOLDER", "/tmp")

    with pytest.raises(ValidationError):
        Settings()
