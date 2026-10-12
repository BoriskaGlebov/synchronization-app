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


def test_lists_nested_files_with_relative_paths_and_skips_part(tmp_path: Path) -> None:
    (tmp_path / "2022" / "05").mkdir(parents=True)
    (tmp_path / "2022" / "05" / "a.jpg").write_text("x")
    (tmp_path / "2022" / "b.jpg.part").write_text("y")

    assert list(LocalStorage(tmp_path).list_files()) == ["2022/05/a.jpg"]


def test_scans_only_requested_subfolders(tmp_path: Path) -> None:
    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "a.jpg").write_text("x")
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "b.jpg").write_text("y")

    assert list(LocalStorage(tmp_path).list_files(["keep", "missing"])) == ["keep/a.jpg"]
