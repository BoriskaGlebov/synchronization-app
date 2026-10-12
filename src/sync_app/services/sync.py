import time

import requests
from loguru import logger

from sync_app.clients.yandex import YandexDiskClient
from sync_app.core.exceptions import SyncError
from sync_app.storage.local import LocalStorage


class SyncService:
    """Сравнивает локальную папку с Яндекс Диском и выравнивает их.

    Если файлов на диске больше, чем локально, лишнее удаляется с диска,
    иначе локальные файлы загружаются или обновляются на диске.

    Args:
        client: Клиент Яндекс Диска.
        storage: Локальное хранилище.
        interval_seconds: Пауза между циклами в режиме демона.
    """

    def __init__(
        self, client: YandexDiskClient, storage: LocalStorage, interval_seconds: int
    ) -> None:
        self.client = client
        self.storage = storage
        self.interval_seconds = interval_seconds

    def run_once(self) -> None:
        """Выполняет один цикл синхронизации."""
        local = self.storage.list_files()
        remote = self.client.list_files()
        if len(local) < len(remote):
            for name in remote.keys() - local.keys():
                self.client.delete(name)
                logger.info("{} - удалён с диска", name)
            return
        for name, info in local.items():
            remote_info = remote.get(name)
            if remote_info is None:
                self.client.upload(self.storage.path_of(name))
                logger.info("{} - загружен на диск", name)
            elif info.size != remote_info.size or info.modified > remote_info.modified:
                self.client.upload(self.storage.path_of(name), overwrite=True)
                logger.info("{} - обновлён на диске", name)

    def run_forever(self) -> None:
        """Запускает циклы синхронизации, пока не возникнет неустранимая ошибка."""
        logger.info("Старт синхронизации: {}", self.storage.root)
        while True:
            try:
                self.run_once()
            except requests.ConnectionError:
                logger.error("Ошибка соединения, повтор через {} с", self.interval_seconds)
            except SyncError as error:
                logger.error("{}", error)
                return
            time.sleep(self.interval_seconds)
