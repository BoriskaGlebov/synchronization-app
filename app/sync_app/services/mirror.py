import asyncio
import contextlib
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from loguru import logger
from yadisk.exceptions import RequestError, UnauthorizedError, YaDiskError

from sync_app.clients.yandex import YandexDisk
from sync_app.core.exceptions import SyncError
from sync_app.core.formatting import human_size
from sync_app.models import FileInfo
from sync_app.services.checks import find_problems
from sync_app.services.mapper import FolderMapper, MappedFiles
from sync_app.services.planner import Download, plan_downloads
from sync_app.storage.local import PART_SUFFIX, LocalStorage


@dataclass(frozen=True, slots=True)
class MirrorResult:
    """Итог одного прохода зеркалирования.

    Attributes:
        planned: Сколько файлов нужно скачать.
        planned_bytes: Суммарный размер файлов к скачиванию.
        downloaded: Сколько скачано успешно.
        failed: Сколько скачать не удалось.
    """

    planned: int
    planned_bytes: int
    downloaded: int
    failed: int


class MirrorService:
    """Односторонне зеркалирует папку Яндекс Диска в локальную папку.

    Файлы только добавляются и обновляются, локальные файлы никогда не удаляются.

    Args:
        disk: Яндекс Диск.
        storage: Локальное хранилище.
        mapper: Соответствие папок Диска и папок назначения.
        interval_seconds: Пауза между проходами в режиме демона.
        concurrency: Максимум одновременных скачиваний.
        report_path: Куда писать подробный отчёт о плане, `None` если не нужен.
    """

    def __init__(
        self,
        disk: YandexDisk,
        storage: LocalStorage,
        mapper: FolderMapper,
        interval_seconds: int,
        concurrency: int,
        report_path: Path | None = None,
    ) -> None:
        self.disk = disk
        self.storage = storage
        self.mapper = mapper
        self.report_path = report_path
        self.interval_seconds = interval_seconds
        self._semaphore = asyncio.Semaphore(concurrency)
        self._sources: dict[str, str] = {}

    async def run_once(self, dry_run: bool = False) -> MirrorResult:
        """Выполняет один проход.

        Args:
            dry_run: Только показать статистику и план, ничего не записывая.

        Raises:
            LocalFolderNotFoundError: Локальной папки нет (например, диск не смонтирован).
        """
        logger.info("Сканирую папку назначения: {}", self.storage.root)
        local = await asyncio.to_thread(self.storage.list_files)
        logger.info(
            "В папке назначения файлов: {}. Получаю список файлов с Яндекс Диска", len(local)
        )
        mapped = self.mapper.map_files(await self.disk.walk_files())
        remote = mapped.files
        plan = plan_downloads(remote, local)
        self._sources = mapped.sources
        planned_bytes = sum(item.remote.size for item in plan)
        logger.info(
            "По соответствиям папок на Диске: {} файлов в {} папках, {}",
            len(remote),
            len({PurePosixPath(path).parent for path in remote}),
            human_size(sum(info.size for info in remote.values())),
        )
        logger.info(
            "К скачиванию: {} файлов в {} папках, {}; уже на месте: {}",
            len(plan),
            len({PurePosixPath(item.path).parent for item in plan}),
            human_size(planned_bytes),
            len(remote) - len(plan),
        )
        problems = {
            item.path: found
            for item in plan
            if (found := find_problems(item.path, item.remote.size))
        }
        self._log_findings(mapped, problems)
        if self.report_path is not None:
            await asyncio.to_thread(self._write_report, plan, remote, local, mapped, problems)
        if dry_run:
            return MirrorResult(len(plan), planned_bytes, 0, 0)
        results = await asyncio.gather(*(self._download(item) for item in plan))
        downloaded = sum(results)
        return MirrorResult(len(plan), planned_bytes, downloaded, len(plan) - downloaded)

    def _log_findings(self, mapped: MappedFiles, problems: dict[str, list[str]]) -> None:
        folders = Counter(PurePosixPath(path).parts[1] for path in mapped.unmapped)
        if folders:
            top = ", ".join(f"{name} ({count})" for name, count in folders.most_common(8))
            logger.warning(
                "Не покрыто соответствиями: {} файлов, папки: {}", len(mapped.unmapped), top
            )
        for skipped, kept in mapped.collisions:
            logger.warning("Конфликт путей: {} пропущен, занято {}", skipped, kept)
        for path, found in list(problems.items())[:20]:
            logger.warning("Проблемный файл {}: {}", path, "; ".join(found))
        if len(problems) > 20:
            logger.warning("Проблемных файлов всего {}, остальные в отчёте", len(problems))
        if self.report_path is not None:
            logger.info("Подробный отчёт: {}", self.report_path)

    def _write_report(
        self,
        plan: list[Download],
        remote: dict[str, FileInfo],
        local: dict[str, FileInfo],
        mapped: MappedFiles,
        problems: dict[str, list[str]],
    ) -> None:
        assert self.report_path is not None
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        planned = {item.path for item in plan}
        lines = [f"# К скачиванию ({len(plan)})"]
        lines += [
            f"{human_size(i.remote.size):>10}  {i.path}  <-  {mapped.sources[i.path]}" for i in plan
        ]
        present = sorted(set(remote) - planned)
        lines += ["", f"# Уже на месте ({len(present)})", *present]
        lines += ["", f"# Проблемные имена ({len(problems)})"]
        lines += [f"{path}: {'; '.join(found)}" for path, found in problems.items()]
        lines += ["", f"# Не покрыто соответствиями ({len(mapped.unmapped)})", *mapped.unmapped]
        lines += ["", f"# Конфликты путей ({len(mapped.collisions)})"]
        lines += [f"{skipped} пропущен, занято {kept}" for skipped, kept in mapped.collisions]
        extra = sorted(
            path
            for path in set(local) - set(remote)
            if any(path.startswith(prefix) for prefix in self.mapper.local_prefixes())
        )
        lines += [
            "",
            f"# Есть локально в папках соответствий, но нет на Диске (не удаляются) ({len(extra)})",
            *extra,
        ]
        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    async def run_forever(self) -> None:
        """Запускает проходы, пока не возникнет неустранимая ошибка."""
        logger.info("Старт зеркалирования в {}", self.storage.root)
        while True:
            try:
                result = await self.run_once()
                logger.info("Скачано {}, ошибок {}", result.downloaded, result.failed)
            except RequestError:
                logger.error("Ошибка соединения, повтор через {} с", self.interval_seconds)
            except UnauthorizedError:
                logger.error("Токен отклонён, выполните `sync-app auth`")
                return
            except SyncError as error:
                logger.error("{}", error)
                return
            await asyncio.sleep(self.interval_seconds)

    async def _download(self, item: Download) -> bool:
        target = self.storage.path_of(item.path)
        part = target.with_name(target.name + PART_SUFFIX)
        async with self._semaphore:
            try:
                await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
                await self.disk.download(self._sources[item.path], part)
                await asyncio.to_thread(self._finalize, item, part, target)
            except UnauthorizedError:
                raise
            except (YaDiskError, OSError, ValueError) as error:
                logger.error("{} - не скачан: {}", item.path, error)
                await asyncio.to_thread(part.unlink, missing_ok=True)
                return False
        logger.info("{} - скачан", item.path)
        return True

    @staticmethod
    def _finalize(item: Download, part: Path, target: Path) -> None:
        size = os.stat(part).st_size
        if size != item.remote.size:
            raise ValueError(f"размер {size} вместо {item.remote.size}")
        timestamp = item.remote.modified.timestamp()
        with contextlib.suppress(OSError):
            os.utime(part, (timestamp, timestamp))
        os.replace(part, target)
