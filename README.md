# Synchronization-app - приложение для синхронизации файлов в папке


### 1. Для работы необходимо установить необходимые зависимости командой 
        pip install -r requirements.txt
![img.png](img.png)
### 2. В файле config.ini необходимо произвести первоначальную настройку параметров
### (путь к папке синхронизации на локальной машине и на удаленном диске, 
### токен, частота синхронизации, путь к файлу с логами) 
### При указании путей необходима запись формата "some_folder/some/folder2/"
![img_1.png](img_1.png)

### 3. При синхронизации пишется лог файл
![img_2.png](img_2.png)
### 4. Для запуска использовать команду 
        python main.py

В ходе своей работы скрипт отслеживает изменения файлов в 
локальной папке, производит своевременную синхронизацию, 
удаление и добавление новых файлов.




