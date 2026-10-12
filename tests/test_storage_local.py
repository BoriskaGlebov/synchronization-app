from pathlib import Path

import pytest
from sync_app.core.exceptions import LocalFolderNotFoundError
from sync_app.storage.local import LocalStorage


def test_lists_only_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("abc")
    (tmp_path / "dir").mkdir()

    files = LocalStorage(tmp_path).list_files()

    assert list(files) == ["a.txt"]
    assert files["a.txt"].size == 3


def test_missing_folder_raises(tmp_path: Path) -> None:
    with pytest.raises(LocalFolderNotFoundError):
        LocalStorage(tmp_path / "nope").list_files()
