import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sync_app.core.settings import FolderMapping
from sync_app.models import FileInfo
from sync_app.services.mapper import FolderMapper
from sync_app.services.mirror import MirrorService
from sync_app.storage.local import LocalStorage
from yadisk.exceptions import YaDiskError

MODIFIED = datetime(2025, 5, 1, 12, 0, tzinfo=UTC)


class FakeDisk:
    def __init__(
        self,
        files: dict[str, bytes],
        broken: set[str] | None = None,
        flaky: dict[str, int] | None = None,
    ) -> None:
        self.files = files
        self.broken = broken or set()
        self.flaky = flaky or {}

    async def walk_files(self, folders: Sequence[str]) -> dict[str, FileInfo]:
        return {path: FileInfo(path, len(data), MODIFIED) for path, data in self.files.items()}

    async def download(self, relative_path: str, destination: Path) -> None:
        if relative_path in self.broken:
            raise YaDiskError("")
        if self.flaky.get(relative_path, 0) > 0:
            self.flaky[relative_path] -= 1
            raise YaDiskError("временный сбой")
        destination.write_bytes(self.files[relative_path])


def make_service(
    disk: FakeDisk,
    root: Path,
    mappings: list[FolderMapping] | None = None,
    report_path: Path | None = None,
) -> MirrorService:
    mapper = FolderMapper(mappings or [FolderMapping(remote="/")])
    return MirrorService(disk, LocalStorage(root), mapper, 1, 2, report_path, 3, 0)  # type: ignore[arg-type]


def test_downloads_into_nested_folders_and_keeps_mtime(tmp_path: Path) -> None:
    disk = FakeDisk({"/2022/05/a.jpg": b"abc"})

    result = asyncio.run(make_service(disk, tmp_path).run_once())

    target = tmp_path / "2022/05/a.jpg"
    assert target.read_bytes() == b"abc"
    assert target.stat().st_mtime == MODIFIED.timestamp()
    assert (result.planned, result.downloaded, result.failed) == (1, 1, 0)
    assert not list(tmp_path.rglob("*.part"))


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    disk = FakeDisk({"/a.jpg": b"abc"})

    result = asyncio.run(make_service(disk, tmp_path).run_once(dry_run=True))

    assert (result.planned, result.planned_bytes, result.downloaded) == (1, 3, 0)
    assert list(tmp_path.iterdir()) == []


def test_second_run_downloads_nothing(tmp_path: Path) -> None:
    service = make_service(FakeDisk({"/a.jpg": b"abc"}), tmp_path)
    asyncio.run(service.run_once())

    assert asyncio.run(service.run_once()).planned == 0


def test_failed_file_does_not_stop_others_and_leaves_no_part(tmp_path: Path) -> None:
    disk = FakeDisk({"/ok.jpg": b"1", "/bad.jpg": b"2"}, broken={"/bad.jpg"})

    result = asyncio.run(make_service(disk, tmp_path).run_once())

    assert (result.downloaded, result.failed) == (1, 1)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ok.jpg"]


def test_keeps_extra_local_files(tmp_path: Path) -> None:
    (tmp_path / "mine.txt").write_text("keep")

    asyncio.run(make_service(FakeDisk({}), tmp_path).run_once())

    assert (tmp_path / "mine.txt").read_text() == "keep"


def test_missing_local_folder_stops_before_anything(tmp_path: Path) -> None:
    from sync_app.core.exceptions import LocalFolderNotFoundError

    service = make_service(FakeDisk({"/a": b"1"}), tmp_path / "not-mounted")

    with pytest.raises(LocalFolderNotFoundError):
        asyncio.run(service.run_once())


def test_unsupported_utime_does_not_fail_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny(*args: object, **kwargs: object) -> None:
        raise PermissionError("utime не поддерживается")

    monkeypatch.setattr("sync_app.services.mirror.os.utime", deny)

    result = asyncio.run(make_service(FakeDisk({"/a.jpg": b"abc"}), tmp_path).run_once())

    assert result.downloaded == 1 and (tmp_path / "a.jpg").read_bytes() == b"abc"


def test_mapping_puts_remote_folder_into_local_subfolder(tmp_path: Path) -> None:
    disk = FakeDisk({"/Фотокамера/2022/a.jpg": b"1", "/Документы/b.pdf": b"2"})
    mappings = [FolderMapping(remote="/Фотокамера", local="Фото/Камера")]

    result = asyncio.run(make_service(disk, tmp_path, mappings).run_once())

    assert (tmp_path / "Фото/Камера/2022/a.jpg").read_bytes() == b"1"
    assert not (tmp_path / "Документы").exists()
    assert result.planned == 1


def test_report_lists_plan_present_and_problems(tmp_path: Path) -> None:
    root = tmp_path / "dest"
    root.mkdir()
    (root / "ok.jpg").write_bytes(b"1")
    disk = FakeDisk({"/Фото/new.jpg": b"22", "/Фото/bad:name.jpg": b"3", "/Другое/x.pdf": b"4"})
    mappings = [FolderMapping(remote="/Фото", local="")]
    report = tmp_path / "report.txt"

    asyncio.run(make_service(disk, root, mappings, report).run_once(dry_run=True))

    text = report.read_text(encoding="utf-8")
    assert "# К скачиванию (2)" in text and "new.jpg  <-  /Фото/new.jpg" in text
    assert "# Проблемные имена (1)" in text and "bad:name.jpg" in text
    assert (
        "# Есть локально в папках соответствий, но нет на Диске (не удаляются) (1)" in text
        and "ok.jpg" in text
    )
    assert not list(root.rglob("new.jpg"))


def test_flaky_file_is_retried_until_it_succeeds(tmp_path: Path) -> None:
    disk = FakeDisk({"/a.jpg": b"abc"}, flaky={"/a.jpg": 2})

    result = asyncio.run(make_service(disk, tmp_path).run_once())

    assert (result.downloaded, result.failed) == (1, 0)
    assert (tmp_path / "a.jpg").read_bytes() == b"abc"


def test_failed_file_is_listed_with_reason(tmp_path: Path) -> None:
    root = tmp_path / "dest"
    root.mkdir()
    disk = FakeDisk({"/bad.jpg": b"1"}, broken={"/bad.jpg"})
    report = tmp_path / "logs" / "report.txt"

    result = asyncio.run(make_service(disk, root, report_path=report).run_once())

    assert result.failures == {"bad.jpg": "YaDiskError"}
    assert "bad.jpg  <-  /bad.jpg: YaDiskError" in (report.parent / "failed.txt").read_text(
        encoding="utf-8"
    )
