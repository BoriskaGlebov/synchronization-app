import datetime
import sys
import time

from folder_script import scaner
from yandex_api import yandex_conn
import logging
from config import configurator
from logging.config import dictConfig
from logger_config import *
from requests.exceptions import ConnectionError

logger = logging.getLogger('main')
sys.excepthook = any_exeption
logging.config.dictConfig(dict_config)


def main():
    logger.info('Старт работы приложения')
    logger.info(f'Синхронизируется папка - {configurator.local_folder}')
    while True:
        try:

            local_files = scaner.list_file()
            remote_files = yandex_conn.get_dick_resources()

            if len(local_files) < len(remote_files):
                for file_name, info in remote_files.items():
                    if file_name not in local_files:
                        yandex_conn.delete(file_name)
                        logger.info(f'{info.path} - Произвел удаление')
            else:
                for file_name, info in local_files.items():
                    if file_name in remote_files:
                        if (info.size != remote_files[file_name].size and
                                info.modified > remote_files[file_name].modified):
                            yandex_conn.reload(file_name)
                            logger.info(f'{info.path} - Произошло обновление файла')
                    elif file_name not in remote_files:
                        yandex_conn.load(file_name)
                        logger.info(f'{info.path} - Загрузил файл на диск')
            time.sleep(int(configurator.timer))
        except (FileNotFoundError, ValueError,ConnectionError,) as ex:
            if type(ex).__name__ == 'FileNotFoundError':
                logger.error(f'{ex.filename} - Такой папки нет , поменяйте название')
            elif type(ex).__name__ == 'ValueError':
                logger.error(f'ошибка в токене')
            elif type(ex).__name__ == 'ConnectionError':
                logger.error(f'Ошибка соединения')
                time.sleep(int(configurator.timer))
                continue
            break
            # raise FileNotFoundError


if __name__ == '__main__':
    main()