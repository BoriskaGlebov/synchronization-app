import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sync_app.models import FileInfo
from sync_app.services.sync import SyncService

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeDisk:
    remote_folder = "/Фото"

    def __init__(self, remote: dict[str, FileInfo]) -> None:
        self.remote = remote
        self.uploaded: list[tuple[str, bool]] = []
        self.removed: list[str] = []

    async def list_files(self) -> dict[str, FileInfo]:
        return self.remote

    async def upload(self, local_path: Path, overwrite: bool = False) -> None:
        self.uploaded.append((local_path.name, overwrite))

    async def remove(self, name: str) -> None:
        self.removed.append(name)


class FakeStorage:
    root = Path("/fake")

    def __init__(self, local: dict[str, FileInfo]) -> None:
        self.local = local

    def list_files(self) -> dict[str, FileInfo]:
        return self.local

    def path_of(self, name: str) -> Path:
        return self.root / name


def make(name: str, size: int = 1, shift: int = 0) -> FileInfo:
    return FileInfo(name, size, NOW + timedelta(seconds=shift))


def run(local: dict[str, FileInfo], remote: dict[str, FileInfo]) -> FakeDisk:
    disk = FakeDisk(remote)
    service = SyncService(disk, FakeStorage(local), 1, 2)  # type: ignore[arg-type]
    asyncio.run(service.run_once())
    return disk


def test_uploads_new_file() -> None:
    disk = run({"a": make("a")}, {})

    assert disk.uploaded == [("a", False)]


def test_overwrites_changed_file() -> None:
    disk = run({"a": make("a", shift=10)}, {"a": make("a")})

    assert disk.uploaded == [("a", True)]


def test_skips_unchanged_file() -> None:
    disk = run({"a": make("a")}, {"a": make("a")})

    assert disk.uploaded == [] and disk.removed == []


def test_deletes_extra_remote_file() -> None:
    disk = run({"a": make("a")}, {"a": make("a"), "b": make("b")})

    assert disk.removed == ["b"]
