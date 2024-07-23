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
        self.local_folder = os.path.abspath(self.local_folder.encode('cp1251').decode('utf8'))
        self.log_path = os.path.abspath(self.log_path.encode('cp1251').decode('utf8'))
        self.remote_folder = self.remote_folder.encode('cp1251').decode('utf8')
        if self.remote_folder.endswith('\\'):
            self.remote_folder = self.remote_folder.replace('\\', '/')
        elif not self.remote_folder.endswith('/'):
            self.remote_folder = self.remote_folder + '/'
        if isinstance(self.timer, str) and self.timer.isdigit():
            self.timer = int(self.timer)
        else:
            raise TypeError("Для таймера необходимо указать целое число")


configurator = ConfigApplication(**res)
if __name__ == '__main__':
    print(configurator.local_folder)
    print(configurator.log_path)
    print(configurator.remote_folder)
    print(configurator.timer)
