import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_USER = "undefined_user"
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> - <level>{level:^10}</level> - "
    "<cyan>{name}</cyan>:<magenta>{line}</magenta> - <yellow>{function}</yellow> - "
    "<magenta>{extra[user]:^15}</magenta> - <white>{message}</white>"
)
ERROR_LEVEL_NO = 30


class LoggerConfig:
    """Настраивает loguru: консоль, основной файл журнала и файл ошибок.

    Args:
        log_dir: Каталог для файлов журнала, создаётся при необходимости.
        logger_level_stdout: Уровень вывода в консоль.
        logger_level_file: Уровень основного файла журнала.
        logger_error_file: Уровень файла ошибок.
        diagnose_files: Включать ли подробную диагностику переменных в файлах.
        extra_defaults: Значения `extra` по умолчанию для всех записей.
    """

    def __init__(
        self,
        log_dir: Path,
        logger_level_stdout: str = "INFO",
        logger_level_file: str = "INFO",
        logger_error_file: str = "WARNING",
        diagnose_files: bool = False,
        extra_defaults: Mapping[str, Any] | None = None,
    ) -> None:
        self.log_dir = log_dir
        self.logger_level_stdout = logger_level_stdout
        self.logger_level_file = logger_level_file
        self.logger_error_file = logger_error_file
        self.diagnose_files = diagnose_files
        self.extra_defaults = dict(extra_defaults or {"user": DEFAULT_USER})
        self.log_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        logger.remove()
        logger.configure(extra=self.extra_defaults)

    @staticmethod
    def _user_filter(record: Mapping[str, Any]) -> bool:
        """Пропускает записи с заданным пользователем."""
        user = record["extra"].get("user")
        return user is not None and user != DEFAULT_USER

    @staticmethod
    def _default_filter(record: Mapping[str, Any]) -> bool:
        """Пропускает записи без пользователя."""
        user = record["extra"].get("user")
        return user is None or user == DEFAULT_USER

    @staticmethod
    def _exclude_errors(record: Mapping[str, Any]) -> bool:
        """Пропускает записи ниже уровня WARNING."""
        return bool(record["level"].no < ERROR_LEVEL_NO)

    def _filter_for_files(self) -> Callable[[Mapping[str, Any]], bool]:
        """Возвращает фильтр основного файла: любые записи кроме ошибок."""

        def _filter(record: Mapping[str, Any]) -> bool:
            return (
                self._user_filter(record) or self._default_filter(record)
            ) and self._exclude_errors(record)

        return _filter

    def setup(self) -> None:
        """Подключает обработчики вывода."""
        logger.add(
            sys.stdout,
            level=self.logger_level_stdout,
            format=LOG_FORMAT,
            enqueue=True,
            catch=True,
            diagnose=self.logger_level_stdout.upper() == "DEBUG",
        )
        logger.add(
            self.log_dir / "file.log",
            level=self.logger_level_file,
            format=LOG_FORMAT,
            rotation="1 day",
            retention="30 days",
            enqueue=True,
            catch=True,
            backtrace=True,
            diagnose=self.diagnose_files,
            filter=self._filter_for_files(),
        )
        logger.add(
            self.log_dir / "error.log",
            level=self.logger_error_file,
            format=LOG_FORMAT,
            rotation="1 day",
            retention="30 days",
            enqueue=True,
            catch=True,
            backtrace=True,
            diagnose=self.diagnose_files,
        )
