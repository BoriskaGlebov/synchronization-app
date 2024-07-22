import datetime
import os
import time
from dataclasses import dataclass
from pprint import pprint

from config import configurator


@dataclass
class Answer:
    name: str
    path: str | None = None
    size: int | None = None
    modified: datetime.datetime | None | str = None

    def __post_init__(self):
        """
        Преобразование времени к нужному формату,
        на ЯД были проблемы с тем что на сервере время в формате UTC,
         а локальное время другое
        """
        if isinstance(self.modified, str):
            self.modified = (datetime.datetime.strptime(self.modified, '%Y-%m-%dT%H:%M:%S%z') -
                             datetime.timedelta(seconds=time.timezone)).replace(tzinfo=None)
        else:
            self.modified = self.modified.replace(microsecond=0)


class FolderScan:
    def __init__(self, path):
        self.path = path

    def list_file(self) -> dict:
        """
        Список из файлов на компе
        :return: список
        """
        scan = os.scandir(self.path)
        some_list = {file.name: Answer(file.name,
                                       file.path,
                                       file.stat().st_size,
                                       datetime.datetime.fromtimestamp(file.stat().st_mtime))
                     for file in scan}
        return some_list


scaner = FolderScan(configurator.local_folder)
if __name__ == '__main__':
    pprint(scaner.list_file())
