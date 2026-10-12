from datetime import UTC, datetime, timedelta
from pathlib import Path

from sync_app.models import FileInfo
from sync_app.services.sync import SyncService

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeClient:
    def __init__(self, remote: dict[str, FileInfo]) -> None:
        self.remote = remote
        self.uploaded: list[tuple[str, bool]] = []
        self.deleted: list[str] = []

    def list_files(self) -> dict[str, FileInfo]:
        return self.remote

    def upload(self, local_path: Path, overwrite: bool = False) -> None:
        self.uploaded.append((local_path.name, overwrite))

    def delete(self, name: str) -> None:
        self.deleted.append(name)


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
    SyncService(client, FakeStorage(local), 1).run_once()  # type: ignore[arg-type]
    return client


def test_uploads_new_file() -> None:
    client = run({"a": make("a")}, {})

    assert client.uploaded == [("a", False)]


def test_overwrites_changed_file() -> None:
    client = run({"a": make("a", shift=10)}, {"a": make("a")})

    assert client.uploaded == [("a", True)]


def test_skips_unchanged_file() -> None:
    client = run({"a": make("a")}, {"a": make("a")})

    assert client.uploaded == [] and client.deleted == []


def test_deletes_extra_remote_file() -> None:
    client = run({"a": make("a")}, {"a": make("a"), "b": make("b")})

    assert client.deleted == ["b"]
