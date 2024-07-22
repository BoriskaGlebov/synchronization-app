import sys
import time
from logging.config import dictConfig

from requests.exceptions import ConnectionError

from folder_script import scaner
from logger_config import *
from yandex_api import yandex_conn

logger = logging.getLogger('main')
sys.excepthook = any_exeption
logging.config.dictConfig(dict_config)


def main():
    """
    Функция запуска основного кода программы
    """
    logger.info('Старт работы приложения')
    logger.info(f'Синхронизируется папка - {configurator.local_folder}')
    while True:
        try:

            local_files = scaner.list_file()
            remote_files = yandex_conn.get_dick_resources()
            remote_flag = True if len(local_files) < len(remote_files) else False
            select_folder = remote_files if remote_flag else local_files
            for file_name, info in select_folder.items():
                if remote_flag and file_name not in local_files:
                    yandex_conn.delete(file_name)
                    logger.info(f'{info.path} - Произвел удаление')
                elif (not remote_flag and
                      file_name in remote_files and
                      (info.size != remote_files[file_name].size or
                       info.modified > remote_files[file_name].modified)
                ):
                    yandex_conn.reload(file_name)
                    logger.info(f'{info.path} - Произошло обновление файла')
                elif not remote_flag and file_name not in remote_files:
                    yandex_conn.load(file_name)
                    logger.info(f'{info.path} - Загрузил файл на диск')

                time.sleep(int(configurator.timer))
        except (FileNotFoundError, ValueError, ConnectionError,) as ex:
            if type(ex).__name__ == 'FileNotFoundError':
                logger.error(f'{ex.filename} - Такой папки нет , поменяйте название локальной папки')
            elif type(ex).__name__ == 'ValueError':
                logger.error(ex)
            elif type(ex).__name__ == 'ConnectionError':
                logger.error(f'Ошибка соединения')
                time.sleep(int(configurator.timer))
                continue
            break


if __name__ == '__main__':
    main()
