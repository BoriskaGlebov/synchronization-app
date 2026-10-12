import asyncio
import contextlib
import os
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from yadisk.exceptions import PathNotFoundError, RequestError, UnauthorizedError, YaDiskError

from sync_app.clients.yandex import YandexDisk
from sync_app.core.exceptions import SyncError
from sync_app.services.planner import Download, plan_downloads
from sync_app.storage.local import PART_SUFFIX, LocalStorage


@dataclass(frozen=True, slots=True)
class MirrorResult:
    """Итог одного прохода зеркалирования.

    Attributes:
        planned: Сколько файлов нужно скачать.
        downloaded: Сколько скачано успешно.
        failed: Сколько скачать не удалось.
    """

    planned: int
    downloaded: int
    failed: int


class MirrorService:
    """Односторонне зеркалирует папку Яндекс Диска в локальную папку.

    Файлы только добавляются и обновляются, локальные файлы никогда не удаляются.

    Args:
        disk: Папка на Яндекс Диске.
        storage: Локальное хранилище.
        interval_seconds: Пауза между проходами в режиме демона.
        concurrency: Максимум одновременных скачиваний.
    """

    def __init__(
        self, disk: YandexDisk, storage: LocalStorage, interval_seconds: int, concurrency: int
    ) -> None:
        self.disk = disk
        self.storage = storage
        self.interval_seconds = interval_seconds
        self._semaphore = asyncio.Semaphore(concurrency)

    async def run_once(self, dry_run: bool = False) -> MirrorResult:
        """Выполняет один проход.

        Args:
            dry_run: Только показать, что будет скачано, ничего не записывая.

        Raises:
            LocalFolderNotFoundError: Локальной папки нет (например, диск не смонтирован).
        """
        local = await asyncio.to_thread(self.storage.list_files)
        remote = await self.disk.walk_files()
        plan = plan_downloads(remote, local)
        logger.info("На диске файлов: {}, к скачиванию: {}", len(remote), len(plan))
        if dry_run:
            for item in plan:
                logger.info("[dry-run] {} ({} байт)", item.path, item.remote.size)
            return MirrorResult(len(plan), 0, 0)
        results = await asyncio.gather(*(self._download(item) for item in plan))
        downloaded = sum(results)
        return MirrorResult(len(plan), downloaded, len(plan) - downloaded)

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
            except PathNotFoundError:
                logger.error("Папка не найдена на Яндекс Диске: {}", self.disk.remote_folder)
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
                await self.disk.download(item.path, part)
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
