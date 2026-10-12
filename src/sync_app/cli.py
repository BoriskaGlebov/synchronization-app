import argparse
from collections.abc import Sequence

from loguru import logger

from sync_app.clients.yandex import YandexDiskClient
from sync_app.core.logger_config import LoggerConfig
from sync_app.core.settings import Settings
from sync_app.services.sync import SyncService
from sync_app.storage.local import LocalStorage


def build_parser() -> argparse.ArgumentParser:
    """Создаёт разбор аргументов командной строки."""
    parser = argparse.ArgumentParser(prog="sync-app", description="Синхронизация с Яндекс Диском")
    parser.add_argument("--once", action="store_true", help="выполнить один цикл и выйти")
    return parser


@logger.catch(reraise=False)
def main(argv: Sequence[str] | None = None) -> None:
    """Точка входа приложения.

    Args:
        argv: Аргументы командной строки, по умолчанию `sys.argv`.
    """
    args = build_parser().parse_args(argv)
    settings = Settings()
    LoggerConfig(
        log_dir=settings.logging.dir,
        logger_level_stdout=settings.logging.level_stdout,
        logger_level_file=settings.logging.level_file,
        logger_error_file=settings.logging.level_error,
    ).setup()
    service = SyncService(
        client=YandexDiskClient(
            settings.yandex_token.get_secret_value(), settings.sync.remote_folder
        ),
        storage=LocalStorage(settings.sync.local_folder),
        interval_seconds=settings.sync.interval_seconds,
    )
    if args.once:
        service.run_once()
    else:
        service.run_forever()


if __name__ == "__main__":
    main()
