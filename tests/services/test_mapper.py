from datetime import UTC, datetime

import pytest
from sync_app.core.settings import FolderMapping
from sync_app.models import FileInfo
from sync_app.services.mapper import FolderMapper

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def mapper(*pairs: tuple[str, str]) -> FolderMapper:
    return FolderMapper([FolderMapping(remote=remote, local=local) for remote, local in pairs])


def test_root_mapping_keeps_structure() -> None:
    assert mapper(("/", "")).target_of("/a/b.jpg") == "a/b.jpg"


def test_folder_mapping_renames_folder() -> None:
    assert mapper(("/Фотокамера", "Фото")).target_of("/Фотокамера/2022/a.jpg") == "Фото/2022/a.jpg"


def test_unmapped_file_is_skipped() -> None:
    assert mapper(("/Фотокамера", "Фото")).target_of("/Книжки/a.pdf") is None


def test_longest_remote_prefix_wins() -> None:
    m = mapper(("/", "Всё"), ("/Фотокамера", "Фото"))

    assert m.target_of("/Фотокамера/a.jpg") == "Фото/a.jpg"
    assert m.target_of("/Книжки/a.pdf") == "Всё/Книжки/a.pdf"


def test_similar_folder_names_do_not_match_by_prefix() -> None:
    assert mapper(("/Фото", "Фото")).target_of("/Фотокамера/a.jpg") is None


def test_parent_reference_is_rejected() -> None:
    with pytest.raises(ValueError):
        mapper(("/", "../outside"))


def test_collision_keeps_first_file() -> None:
    m = mapper(("/A", "X"), ("/B", "X"))
    remote = {"/A/f.jpg": FileInfo("/A/f.jpg", 1, NOW), "/B/f.jpg": FileInfo("/B/f.jpg", 2, NOW)}

    mapped = m.map_files(remote)

    assert mapped.sources == {"X/f.jpg": "/A/f.jpg"}
