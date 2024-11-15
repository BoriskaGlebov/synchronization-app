# Словарь настройки логирования проекта
import logging
import os.path
from logging import config

from config import configurator

# default_path = os.path.dirname(os.path.abspath(__file__)).split('synchronization-app')[0] + 'synchronization-app/'
default_path = os.path.abspath(configurator.log_path)
if not os.path.exists(default_path):
    raise FileNotFoundError("Нет такой папки для логера, поменяйте название")
# print(os.path.join(default_path, 'logger.log'))

def any_exeption(type, values, traceback_info):
    """
    Функция логгирования неожиданных исключений
    :param type:
    :param values:
    :param traceback_info:
    :return:
    """
    logger = logging.getLogger('main')
    logging.config.dictConfig(dict_config)
    logger.error(f'some error {type} {values} {traceback_info}', exc_info=(type, values, traceback_info))


dict_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "base": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | line %(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "base"

        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "base",
            "filename": os.path.join(default_path, 'logger.log'),
            "mode": "a",
            "encoding": "utf-8",
        },

    },
    "loggers": {
        "main": {
            "level": "INFO",
            "handlers": ["file", "console"],
        },

    },
    # "filters": {
    #     "my_filter": {
    #         "()": SelfFilter,
    #     }
    # },
    # "root":{},
}
