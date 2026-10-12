import asyncio

from loguru import logger
from yadisk import AsyncClient
from yadisk.exceptions import PathNotFoundError, RequestError, UnauthorizedError

from sync_app.clients.yandex import list_files
from sync_app.core.exceptions import SyncError
from sync_app.storage.local import LocalStorage


class SyncService:
    """Сравнивает локальную папку с Яндекс Диском и выравнивает их.

    Если файлов на диске больше, чем локально, лишнее удаляется с диска,
    иначе локальные файлы загружаются или обновляются на диске.

    Args:
        client: Асинхронный клиент Яндекс Диска.
        storage: Локальное хранилище.
        remote_folder: Папка на Яндекс Диске.
        interval_seconds: Пауза между циклами в режиме демона.
        concurrency: Максимум одновременных передач файлов.
    """

    def __init__(
        self,
        client: AsyncClient,
        storage: LocalStorage,
        remote_folder: str,
        interval_seconds: int,
        concurrency: int,
    ) -> None:
        self.client = client
        self.storage = storage
        self.remote_folder = "/" + remote_folder.strip("/")
        self.interval_seconds = interval_seconds
        self._semaphore = asyncio.Semaphore(concurrency)

    async def run_once(self) -> None:
        """Выполняет один цикл синхронизации."""
        local = await asyncio.to_thread(self.storage.list_files)
        remote = await list_files(self.client, self.remote_folder)
        if len(local) < len(remote):
            await asyncio.gather(*(self._delete(name) for name in remote.keys() - local.keys()))
            return
        tasks = []
        for name, info in local.items():
            remote_info = remote.get(name)
            if remote_info is None:
                tasks.append(self._upload(name, overwrite=False))
            elif info.size != remote_info.size or info.modified > remote_info.modified:
                tasks.append(self._upload(name, overwrite=True))
        await asyncio.gather(*tasks)

    async def run_forever(self) -> None:
        """Запускает циклы синхронизации, пока не возникнет неустранимая ошибка."""
        logger.info("Старт синхронизации: {}", self.storage.root)
        while True:
            try:
                await self.run_once()
            except RequestError:
                logger.error("Ошибка соединения, повтор через {} с", self.interval_seconds)
            except UnauthorizedError:
                logger.error("Токен отклонён, выполните `sync-app auth`")
                return
            except PathNotFoundError:
                logger.error("Папка не найдена на Яндекс Диске: {}", self.remote_folder)
                return
            except SyncError as error:
                logger.error("{}", error)
                return
            await asyncio.sleep(self.interval_seconds)

    async def _upload(self, name: str, overwrite: bool) -> None:
        async with self._semaphore:
            await self.client.upload(
                str(self.storage.path_of(name)),
                f"{self.remote_folder.rstrip('/')}/{name}",
                overwrite=overwrite,
            )
        logger.info("{} - {} на диске", name, "обновлён" if overwrite else "загружен")

    async def _delete(self, name: str) -> None:
        async with self._semaphore:
            await self.client.remove(f"{self.remote_folder.rstrip('/')}/{name}", permanently=False)
        logger.info("{} - удалён с диска (в корзину)", name)
