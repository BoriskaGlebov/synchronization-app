from pathlib import Path

import pytest


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(
        '[sync]\nremote_folder = "/Фото"\nlocal_folder = "/mnt/nas"\ninterval_seconds = 15\n'
        '[logging]\nlevel_stdout = "DEBUG"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("SYNC_CONFIG", str(path))
    monkeypatch.chdir(tmp_path)
    return path
