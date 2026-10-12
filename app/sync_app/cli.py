import argparse
import asyncio
from collections.abc import Sequence

from loguru import logger

from sync_app.clients.yandex import TokenStore, authorize, build_client, ensure_token
from sync_app.core.logger_config import LoggerConfig
from sync_app.core.settings import Settings
from sync_app.services.sync import SyncService
from sync_app.storage.local import LocalStorage


def build_parser() -> argparse.ArgumentParser:
    """Создаёт разбор аргументов командной строки."""
    parser = argparse.ArgumentParser(prog="sync-app", description="Синхронизация с Яндекс Диском")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("auth", help="получить OAuth-токен по коду подтверждения")
    run = subparsers.add_parser("run", help="синхронизировать (команда по умолчанию)")
    run.add_argument("--once", action="store_true", help="выполнить один цикл и выйти")
    return parser


async def _run(settings: Settings, command: str, once: bool) -> None:
    client = build_client(settings)
    store = TokenStore(settings.auth.token_file)
    async with client:
        if command == "auth":
            await authorize(client, store, settings.auth.redirect_uri)
            logger.info("Токен сохранён: {}", store.path)
            return
        await ensure_token(client, store)
        service = SyncService(
            client=client,
            storage=LocalStorage(settings.sync.local_folder),
            remote_folder=settings.sync.remote_folder,
            interval_seconds=settings.sync.interval_seconds,
            concurrency=settings.sync.concurrency,
        )
        if once:
            await service.run_once()
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
    asyncio.run(_run(settings, args.command or "run", getattr(args, "once", False)))


if __name__ == "__main__":
    main()
