import configparser
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


configurator = ConfigApplication(**res)
# print(configurator)