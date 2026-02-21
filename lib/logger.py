import json
import logging
import os
from datetime import datetime
from pathlib import Path


try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def get_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    Get a configured logger for UltiPlate services.

    Args:
        service_name: Name of the service/module
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.propagate = False
    logging.raiseExceptions = False

    if not logger.handlers:
        # Console handler with JSON formatting
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter(service_name))
        logger.addHandler(handler)

        # File handler - writes to logs directory
        logs_dir = Path(os.getenv("LOGDIR", "./logs"))
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logs_dir / f"{service_name}.log")
        file_handler.setFormatter(JsonFormatter(service_name))
        logger.addHandler(file_handler)

    return logger


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)
