import argparse
import asyncio
from collections.abc import Sequence

from loguru import logger

from sync_app.clients.yandex import YandexDisk
from sync_app.core.logger_config import LoggerConfig
from sync_app.core.settings import Settings
from sync_app.services.mapper import FolderMapper
from sync_app.services.mirror import MirrorService
from sync_app.storage.local import LocalStorage


def build_parser() -> argparse.ArgumentParser:
    """Создаёт разбор аргументов командной строки."""
    parser = argparse.ArgumentParser(prog="sync-app", description="Синхронизация с Яндекс Диском")
    subparsers = parser.add_subparsers(dest="command", description="Команды")
    auth_help = "получить OAuth-токен по коду подтверждения"
    run_help = "синхронизировать (команда по умолчанию)"
    subparsers.add_parser("auth", help=auth_help, description=auth_help)
    run = subparsers.add_parser("run", help=run_help, description=run_help)
    run.add_argument("--once", action="store_true", help="выполнить один цикл и выйти")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="показать статистику (файлы, папки, размер), ничего не скачивая",
    )
    return parser


async def _run(settings: Settings, command: str, once: bool, dry_run: bool) -> None:
    async with YandexDisk.from_settings(settings) as disk:
        if command == "auth":
            await disk.authorize()
            logger.info("Токен сохранён: {}", disk.store.path)
            return
        await disk.ensure_token()
        service = MirrorService(
            disk=disk,
            storage=LocalStorage(settings.sync.local_folder),
            mapper=FolderMapper(settings.sync.mappings),
            interval_seconds=settings.sync.interval_seconds,
            concurrency=settings.sync.concurrency,
        )
        if once or dry_run:
            await service.run_once(dry_run=dry_run)
        else:
            await service.run_forever()


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
    asyncio.run(
        _run(
            settings,
            args.command or "run",
            getattr(args, "once", False),
            getattr(args, "dry_run", False),
        )
    )


if __name__ == "__main__":
    main()
