from pathlib import Path

import pytest
from pydantic import ValidationError
from sync_app.core.settings import PROJECT_ROOT, Settings


@pytest.fixture
def secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_YANDEX_CLIENT_ID", "client-id")
    monkeypatch.setenv("SYNC_YANDEX_CLIENT_SECRET", "top-secret")


@pytest.mark.usefixtures("config_file", "secrets")
def test_reads_toml_and_secrets_from_env() -> None:
    settings = Settings()

    assert settings.yandex_client_id == "client-id"
    assert settings.yandex_client_secret.get_secret_value() == "top-secret"
    assert [(m.remote, m.local) for m in settings.sync.mappings] == [("/Фото", "Фото")]
    assert settings.sync.local_folder == Path("/mnt/nas")
    assert settings.sync.interval_seconds == 15
    assert settings.sync.concurrency == 5
    assert settings.logging.level_stdout == "DEBUG"
    assert settings.auth.token_file == PROJECT_ROOT / "secrets/token.json"


@pytest.mark.usefixtures("config_file", "secrets")
def test_env_overrides_toml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_SYNC__INTERVAL_SECONDS", "5")

    assert Settings().sync.interval_seconds == 5


@pytest.mark.usefixtures("config_file", "secrets")
def test_secret_is_hidden_in_repr() -> None:
    assert "top-secret" not in repr(Settings())


@pytest.mark.usefixtures("config_file")
def test_requires_client_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNC_YANDEX_CLIENT_ID", raising=False)
    monkeypatch.delenv("SYNC_YANDEX_CLIENT_SECRET", raising=False)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.usefixtures("config_file", "secrets")
def test_default_paths_do_not_depend_on_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert Settings().logging.dir == PROJECT_ROOT / "logs"
