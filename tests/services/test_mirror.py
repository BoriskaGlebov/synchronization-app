import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sync_app.models import FileInfo
from sync_app.services.mirror import MirrorService
from sync_app.storage.local import LocalStorage
from yadisk.exceptions import YaDiskError

MODIFIED = datetime(2025, 5, 1, 12, 0, tzinfo=UTC)


class FakeDisk:
    remote_folder = "/Фото"

    def __init__(self, files: dict[str, bytes], broken: set[str] | None = None) -> None:
        self.files = files
        self.broken = broken or set()

    async def walk_files(self) -> dict[str, FileInfo]:
        return {path: FileInfo(path, len(data), MODIFIED) for path, data in self.files.items()}

    async def download(self, relative_path: str, destination: Path) -> None:
        if relative_path in self.broken:
            raise YaDiskError("boom")
        destination.write_bytes(self.files[relative_path])


def make_service(disk: FakeDisk, root: Path) -> MirrorService:
    return MirrorService(disk, LocalStorage(root), 1, 2)  # type: ignore[arg-type]


def test_downloads_into_nested_folders_and_keeps_mtime(tmp_path: Path) -> None:
    disk = FakeDisk({"2022/05/a.jpg": b"abc"})

    result = asyncio.run(make_service(disk, tmp_path).run_once())

    target = tmp_path / "2022/05/a.jpg"
    assert target.read_bytes() == b"abc"
    assert target.stat().st_mtime == MODIFIED.timestamp()
    assert (result.planned, result.downloaded, result.failed) == (1, 1, 0)
    assert not list(tmp_path.rglob("*.part"))


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    disk = FakeDisk({"a.jpg": b"abc"})

    result = asyncio.run(make_service(disk, tmp_path).run_once(dry_run=True))

    assert result.planned == 1 and result.downloaded == 0
    assert list(tmp_path.iterdir()) == []


def test_second_run_downloads_nothing(tmp_path: Path) -> None:
    service = make_service(FakeDisk({"a.jpg": b"abc"}), tmp_path)
    asyncio.run(service.run_once())

    assert asyncio.run(service.run_once()).planned == 0


def test_failed_file_does_not_stop_others_and_leaves_no_part(tmp_path: Path) -> None:
    disk = FakeDisk({"ok.jpg": b"1", "bad.jpg": b"2"}, broken={"bad.jpg"})

    result = asyncio.run(make_service(disk, tmp_path).run_once())

    assert (result.downloaded, result.failed) == (1, 1)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ok.jpg"]


def test_keeps_extra_local_files(tmp_path: Path) -> None:
    (tmp_path / "mine.txt").write_text("keep")

    asyncio.run(make_service(FakeDisk({}), tmp_path).run_once())

    assert (tmp_path / "mine.txt").read_text() == "keep"


def test_missing_local_folder_stops_before_anything(tmp_path: Path) -> None:
    from sync_app.core.exceptions import LocalFolderNotFoundError

    service = make_service(FakeDisk({"a": b"1"}), tmp_path / "not-mounted")

    with pytest.raises(LocalFolderNotFoundError):
        asyncio.run(service.run_once())
