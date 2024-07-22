import configparser
import os.path
from dataclasses import dataclass

conf = configparser.ConfigParser()
with open('config.ini') as fp:
    conf.read_file(fp)
    res = {k: v for k, v in conf.items('yandex_config')}
    # print(res)


@dataclass
class ConfigApplication:
    """
    Хранит параметры для настройки приложения
    """
    token: str
    remote_folder: str
    local_folder: str
    timer: int | None = None
    log_path: str | None = None

    def __post_init__(self):
        self.local_folder = os.path.abspath(self.local_folder)
        self.log_path = os.path.abspath(self.log_path)
        if self.remote_folder.endswith('\\'):
            self.remote_folder = self.remote_folder.replace('\\', '/')
        elif not self.remote_folder.endswith('/'):
            self.remote_folder = self.remote_folder + '/'


configurator = ConfigApplication(**res)
# print(configurator.local_folder)
# print(configurator.log_path)
# print(configurator.remote_folder)
