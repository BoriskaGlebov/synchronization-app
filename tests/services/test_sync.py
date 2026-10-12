import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sync_app.models import FileInfo
from sync_app.services.sync import SyncService

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeClient:
    def __init__(self, remote: dict[str, FileInfo]) -> None:
        self.remote = remote
        self.uploaded: list[tuple[str, bool]] = []
        self.removed: list[str] = []

    async def listdir(self, path: str) -> AsyncIterator[SimpleNamespace]:
        for info in self.remote.values():
            yield SimpleNamespace(
                name=info.name, size=info.size, modified=info.modified, type="file"
            )

    async def upload(self, src: str, dst: str, overwrite: bool = False) -> None:
        self.uploaded.append((Path(src).name, overwrite))

    async def remove(self, path: str, permanently: bool = True) -> None:
        self.removed.append(Path(path).name)


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


def run(local: dict[str, FileInfo], remote: dict[str, FileInfo]) -> FakeClient:
    client = FakeClient(remote)
    service = SyncService(client, FakeStorage(local), "/Фото", 1, 2)  # type: ignore[arg-type]
    asyncio.run(service.run_once())
    return client


def test_uploads_new_file() -> None:
    client = run({"a": make("a")}, {})

    assert client.uploaded == [("a", False)]


def test_overwrites_changed_file() -> None:
    client = run({"a": make("a", shift=10)}, {"a": make("a")})

    assert client.uploaded == [("a", True)]


def test_skips_unchanged_file() -> None:
    client = run({"a": make("a")}, {"a": make("a")})

    assert client.uploaded == [] and client.removed == []


def test_deletes_extra_remote_file() -> None:
    client = run({"a": make("a")}, {"a": make("a"), "b": make("b")})

    assert client.removed == ["b"]
