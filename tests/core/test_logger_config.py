from pathlib import Path

from loguru import logger
from sync_app.core.logger_config import LoggerConfig


def test_writes_info_to_file_and_errors_to_error_log(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    LoggerConfig(log_dir=log_dir).setup()

    logger.info("обычная запись")
    logger.error("ошибка")
    logger.complete()
    logger.remove()

    assert "обычная запись" in (log_dir / "file.log").read_text(encoding="utf-8")
    assert "ошибка" not in (log_dir / "file.log").read_text(encoding="utf-8")
    assert "ошибка" in (log_dir / "error.log").read_text(encoding="utf-8")
