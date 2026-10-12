from datetime import UTC, datetime

from sync_app.models import FileInfo
from sync_app.services.planner import plan_downloads

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def info(path: str, size: int = 1) -> FileInfo:
    return FileInfo(path, size, NOW)


def test_downloads_missing_file() -> None:
    plan = plan_downloads({"a/1.jpg": info("a/1.jpg")}, {})

    assert [item.path for item in plan] == ["a/1.jpg"]


def test_downloads_file_with_different_size() -> None:
    plan = plan_downloads({"a": info("a", 2)}, {"a": info("a", 1)})

    assert [item.path for item in plan] == ["a"]


def test_skips_identical_file() -> None:
    assert plan_downloads({"a": info("a")}, {"a": info("a")}) == []


def test_never_plans_deletion_of_extra_local_files() -> None:
    assert plan_downloads({}, {"extra": info("extra")}) == []
