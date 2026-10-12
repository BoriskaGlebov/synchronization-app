import asyncio
import contextlib
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from loguru import logger
from yadisk.exceptions import RequestError, UnauthorizedError, YaDiskError

from sync_app.clients.yandex import YandexDisk
from sync_app.core.exceptions import SyncError
from sync_app.core.formatting import describe_error, human_size
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
        failures: Причина неудачи по пути файла.
    """

    planned: int
    planned_bytes: int
    downloaded: int
    failed: int
    failures: dict[str, str] = field(default_factory=dict)


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
        attempts: Сколько раз пробовать скачать файл при ошибке.
        retry_delay: Пауза перед повтором в секундах, растёт с номером попытки.
    """

    def __init__(
        self,
        disk: YandexDisk,
        storage: LocalStorage,
        mapper: FolderMapper,
        interval_seconds: int,
        concurrency: int,
        report_path: Path | None = None,
        attempts: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.disk = disk
        self.storage = storage
        self.mapper = mapper
        self.report_path = report_path
        self.attempts = attempts
        self.retry_delay = retry_delay
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
        local = await asyncio.to_thread(self.storage.list_files, self.mapper.local_folders())
        logger.info(
            "В папке назначения файлов: {}. Получаю список файлов с Яндекс Диска", len(local)
        )
        mapped = self.mapper.map_files(await self.disk.walk_files(self.mapper.remote_folders()))
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
        errors = await asyncio.gather(*(self._download(item) for item in plan))
        failures = {item.path: error for item, error in zip(plan, errors, strict=True) if error}
        if failures:
            await asyncio.to_thread(self._write_failures, plan, failures)
        result = MirrorResult(
            len(plan), planned_bytes, len(plan) - len(failures), len(failures), failures
        )
        logger.info("Готово: скачано {}, не скачано {}", result.downloaded, result.failed)
        return result

    def _log_findings(self, mapped: MappedFiles, problems: dict[str, list[str]]) -> None:
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
        lines += ["", f"# Конфликты путей ({len(mapped.collisions)})"]
        lines += [f"{skipped} пропущен, занято {kept}" for skipped, kept in mapped.collisions]
        extra = sorted(set(local) - set(remote))
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
                await self.run_once()
            except RequestError:
                logger.error("Ошибка соединения, повтор через {} с", self.interval_seconds)
            except UnauthorizedError:
                logger.error("Токен отклонён, выполните `sync-app auth`")
                return
            except SyncError as error:
                logger.error("{}", error)
                return
            await asyncio.sleep(self.interval_seconds)

    async def _download(self, item: Download) -> str | None:
        """Скачивает файл с повторами. Возвращает причину неудачи или `None` при успехе."""
        target = self.storage.path_of(item.path)
        part = target.with_name(target.name + PART_SUFFIX)
        error = ""
        for attempt in range(1, self.attempts + 1):
            async with self._semaphore:
                try:
                    await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
                    await self.disk.download(self._sources[item.path], part)
                    await asyncio.to_thread(self._finalize, item, part, target)
                except UnauthorizedError:
                    raise
                except (YaDiskError, OSError, ValueError) as exc:
                    error = describe_error(exc)
                    await asyncio.to_thread(part.unlink, missing_ok=True)
                else:
                    logger.info("{} - скачан", item.path)
                    return None
            logger.warning("{} - попытка {}/{}: {}", item.path, attempt, self.attempts, error)
            if attempt < self.attempts:
                await asyncio.sleep(self.retry_delay * attempt)
        logger.error("{} - не скачан: {}", item.path, error)
        return error

    def _write_failures(self, plan: list[Download], failures: dict[str, str]) -> None:
        if self.report_path is None:
            return
        sizes = {item.path: item.remote.size for item in plan}
        lines = [f"# Не скачано ({len(failures)})"]
        lines += [
            f"{human_size(sizes[path]):>10}  {path}  <-  {self._sources[path]}: {reason}"
            for path, reason in failures.items()
        ]
        failed_path = self.report_path.with_name("failed.txt")
        failed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.error("Список нескачанных файлов: {}", failed_path)

    @staticmethod
    def _finalize(item: Download, part: Path, target: Path) -> None:
        size = os.stat(part).st_size
        if size != item.remote.size:
            raise ValueError(f"размер {size} вместо {item.remote.size}")
        timestamp = item.remote.modified.timestamp()
        with contextlib.suppress(OSError):
            os.utime(part, (timestamp, timestamp))
        os.replace(part, target)
