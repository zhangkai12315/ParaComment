"""Lightweight JSON-lines debug logging for runtime diagnostics."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from app.config import get_debug_log_path


class DebugLogger:
    """Append structured diagnostic records to a per-user log file."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        self._path = Path(log_path) if log_path else get_debug_log_path()
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def log(self, event: str, **fields: object) -> None:
        record = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "pid": os.getpid(),
            "event": event,
        }
        if fields:
            record["fields"] = self._normalize(fields)

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, ensure_ascii=False)
            with self._lock, self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def _normalize(self, value: object) -> object:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): self._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._normalize(item) for item in value]
        return repr(value)
