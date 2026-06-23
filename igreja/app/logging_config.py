import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import threading
from pathlib import Path

from app.version import APP_NAME


def log_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Logs")
    else:
        base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_NAME / "logs"


def configure_logging() -> Path:
    target_dir = log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / "igreja.log"
    root_logger = logging.getLogger()
    if any(getattr(handler, "_igreja_handler", False) for handler in root_logger.handlers):
        return log_path

    handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler._igreja_handler = True
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    def log_uncaught_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("uncaught").critical(
            "Excecao nao tratada.",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def log_thread_exception(args):
        logging.getLogger("threading").critical(
            "Excecao nao tratada na thread %s.",
            getattr(args.thread, "name", "desconhecida"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = log_uncaught_exception
    threading.excepthook = log_thread_exception
    return log_path
