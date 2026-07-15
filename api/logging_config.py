"""
logging_config.py - Logs structures JSON pour l'API Waterflow 2.

Un log = un evenement avec contexte (event + champs via extra=...), jamais un
print() : necessaire pour filtrer/agreger les logs en cas d'incident (voir
docs/incidents/).
"""

import json
import logging
import sys

_STANDARD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
}


class JSONFormatter(logging.Formatter):
    """Formate chaque LogRecord en une ligne JSON (event + champs extra=...)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        return json.dumps(payload, default=str)


def _configure_logging() -> logging.Logger:
    log = logging.getLogger("waterflow2")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


logger = _configure_logging()
