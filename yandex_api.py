import datetime

import requests
from pprint import pprint
from folder_script import Answer
from config import configurator


class YandexApi:
    """
    Класс работы с APi Яндекс диска
    """
    def __init__(self, token):
        self.token = token
        self.header = {'Accept': 'application/json',
                       'Content-Type': 'application/json',
                       'Authorization': f'OAuth {self.token}'}

    def get_info_disc(self) -> dict | int:
        """
        Получение информации о диске, проверяю что это нужный диск
        :return:dict|status_code
        """
        http = 'https://cloud-api.yandex.net/v1/disk'
        data = {'fields': 'user'}
        response = requests.get(url=http, headers=self.header, params=data)
        print(response.url)
        if response.status_code == 200:
            return response.json()
        return response.status_code

    def get_dick_resources(self) -> dict | int:
        """
        Показывает содержимое папки с файлами
        :return: список файлов с их данными
        """
        http = 'https://cloud-api.yandex.net/v1/disk/resources'
        data = {'path': '/test/',
                'fields': '_embedded.items.name, '
                          '_embedded.items.path, '
                          '_embedded.items.size, '
                          '_embedded.items.modified',
                }
        response = requests.get(url=http, headers=self.header, params=data)
        if response.status_code == 200:
            res = {file['name']: Answer(**file)
                   for file in response.json()['_embedded']['items']}

            return res
        elif response.status_code == 401:
            raise ValueError("Ошибка в токене")
        return response.status_code

    def load(self, path) -> int | str:
        """
        Загрузка нового файла
        :param path: путь куда грузить
        :return: статус код или код ошибки
        """
        http = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        params = {'path': configurator.remote_folder + path,
                  'overwrite': False}
        response = requests.get(url=http, headers=self.header, params=params)

        if response.status_code == 200:
            href = response.json()['href']
            with open(configurator.local_folder + path, 'rb') as file:
                res = requests.put(url=href, files={'file': file})
                if (status_code := res.status_code) == 201:
                    return status_code
        else:
            return response.json()['message']

    def reload(self, path) -> int | str:
        """
        Обновление данных файла

        :param path: путь к файлу
        :return: статус код или сообщение об ошибке
        """
        http = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        params = {'path': configurator.remote_folder + path,
                  'overwrite': True}
        response = requests.get(url=http, headers=self.header, params=params)

        if response.status_code == 200:
            href = response.json()['href']
            with open(configurator.local_folder + path, 'rb') as file:
                res = requests.put(url=href, files={'file': file})
                if (status_code := res.status_code) == 201:
                    return status_code
        else:
            return response.json()['message']

    def delete(self, filename) -> None | int:
        """
        Удаляю диск по названию
        :param filename: имя файла в удаленной папке
        :return: статус код или ничего
        """
        http = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {'path': configurator.remote_folder + filename}
        response = requests.delete(url=http, headers=self.header, params=params)
        # print(params)
        # print(response.url)
        if response.status_code == 204:
            return None
        else:
            return response.status_code


yandex_conn = YandexApi(configurator.token)
if __name__ == '__main__':
    pprint(yandex_conn.get_info_disc())
    pprint(yandex_conn.get_dick_resources())
    # pprint(yandex_conn.load('ex.txt'))
    # pprint(yandex_conn.reload('ex.txt'))
    # pprint(yandex_conn.delete('ex1.txt'))
