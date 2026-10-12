# synchronization-app

Зеркалирование папки Яндекс Диска на локальный или сетевой диск.

## Структура

```
config/settings.toml      несекретные настройки
.env                      секреты (SYNC_YANDEX_TOKEN), не коммитится
app/sync_app/
  cli.py                  точка входа
  core/                   настройки, логирование, исключения
  clients/yandex.py       клиент API Яндекс Диска
  storage/local.py        локальная папка или сетевой диск
  services/mapper.py      соответствие папок Диска и папок назначения
  services/planner.py     что скачать (чистая логика)
  services/mirror.py      зеркалирование Яндекс Диск -> локальная папка
tests/                    pytest
docs/img/                 иллюстрации
```

## Установка

```
poetry install
poetry run pre-commit install
cp .env.example .env   # вписать SYNC_YANDEX_TOKEN
```

Пути и интервал задаются в `config/settings.toml`. Любой параметр можно переопределить
переменной окружения: `SYNC_SYNC__INTERVAL_SECONDS=30`. Другой файл настроек: `SYNC_CONFIG=/path/settings.toml`.

## Соответствие папок

В `config/settings.toml` блоки `[[sync.mappings]]` задают, какую папку Диска в какую подпапку
`local_folder` копировать. Без блоков копируется весь диск с сохранением структуры.

```toml
[[sync.mappings]]
remote = "/Фотокамера"
local = "Фото/Камера"
```

Для файла выбирается самое длинное подходящее соответствие. Файлы вне соответствий пропускаются.
Файл скачивается, только если по пути назначения его нет или отличается размер.

## Запуск

Коротко через make: `make install`, `make auth`, `make run`, `make once`, `make dry`, `make test`, `make check`.

```
poetry run sync-app          # демон
poetry run sync-app --once   # один цикл
```

Логи пишутся в каталог `logging.dir`: `file.log` (без ошибок) и `error.log` (WARNING и выше).

## Разработка

```
poetry run pytest
poetry run pre-commit run --all-files
```
