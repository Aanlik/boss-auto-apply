from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.services.workflow_persistence import DATA_DIR


_configured = False


def configure_runtime_logging(data_dir: Path | None = None) -> Path:
    """Persist diagnostic logs for packaged and development runs."""
    global _configured
    root = (data_dir or DATA_DIR) / "logs"
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "runtime.log"
    if _configured:
        return log_path

    level_name = os.environ.get("BOSS_WORKBENCH_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    logging.captureWarnings(True)
    sys.excepthook = _uncaught_exception
    _configured = True
    logging.getLogger(__name__).info("运行日志已启用: %s", log_path)
    return log_path


def _uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger("uncaught_exception").critical(
        "未捕获异常: %s",
        exc_value,
        exc_info=(exc_type, exc_value, exc_traceback),
    )
