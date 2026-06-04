"""Persistence for file progress and app-level state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.config import (
    DEFAULT_COMMENT_STYLE,
    DEFAULT_OUTPUT_MODE,
    DEFAULT_PASTE_MODE,
    DEFAULT_SMART_CHUNK_LENGTH,
    get_state_file_path,
)
from app.hotkeys import serialize_hotkey_specs
from app.models import FileProgress
from app.services.text_loader import validate_smart_chunk_length


class StateStore:
    """Read and write application state as JSON."""

    def __init__(self, state_path: str | Path | None = None) -> None:
        self.state_path = Path(state_path) if state_path else get_state_file_path()

    def load(self) -> dict:
        if not self.state_path.exists():
            return _default_state()

        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return _default_state()

    def save(self, data: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.state_path.parent,
            suffix=".tmp",
        ) as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            temp_path = Path(handle.name)
        os.replace(temp_path, self.state_path)

    def get_recent_file(self) -> Path | None:
        data = self.load()
        recent = data.get("recent_file")
        if not recent:
            return None
        return Path(recent)

    def set_recent_file(self, path: str | Path) -> None:
        data = self.load()
        data["recent_file"] = str(Path(path))
        data["recent_files"] = _updated_recent_files(data.get("recent_files"), path)
        self.save(data)

    def get_recent_files(self) -> list[Path]:
        data = self.load()
        recent_files = data.get("recent_files", [])
        if not isinstance(recent_files, list):
            return []
        return [Path(str(path)) for path in recent_files if path]

    def load_hotkeys(self) -> dict:
        data = self.load()
        hotkeys = data.get("hotkeys", {})
        return hotkeys if isinstance(hotkeys, dict) else {}

    def save_hotkeys(self, specs) -> None:
        data = self.load()
        data["hotkeys"] = serialize_hotkey_specs(list(specs))
        self.save(data)

    def load_settings(self) -> dict[str, bool | int | str]:
        data = self.load()
        settings = data.get("settings", {})
        if not isinstance(settings, dict):
            settings = {}

        output_mode = settings.get("default_output_mode", DEFAULT_OUTPUT_MODE)
        if output_mode not in {"paragraph", "smart"}:
            output_mode = DEFAULT_OUTPUT_MODE

        smart_chunk_length = validate_smart_chunk_length(
            _coerce_int(settings.get("default_smart_chunk_length"), DEFAULT_SMART_CHUNK_LENGTH)
        )
        paste_mode = _coerce_paste_mode(settings.get("default_paste_mode"), DEFAULT_PASTE_MODE)
        restore_clipboard = bool(settings.get("restore_clipboard_after_paste", False))

        return {
            "default_output_mode": output_mode,
            "default_smart_chunk_length": smart_chunk_length,
            "default_paste_mode": paste_mode,
            "restore_clipboard_after_paste": restore_clipboard,
        }

    def save_settings(
        self,
        output_mode: str,
        smart_chunk_length: int,
        paste_mode: str,
        restore_clipboard_after_paste: bool | None = None,
    ) -> None:
        data = self.load()
        current_settings = data.get("settings", {})
        if not isinstance(current_settings, dict):
            current_settings = {}
        if restore_clipboard_after_paste is None:
            restore_clipboard_after_paste = bool(current_settings.get("restore_clipboard_after_paste", False))
        data["settings"] = {
            "default_output_mode": output_mode if output_mode in {"paragraph", "smart"} else DEFAULT_OUTPUT_MODE,
            "default_smart_chunk_length": validate_smart_chunk_length(smart_chunk_length),
            "default_paste_mode": _coerce_paste_mode(paste_mode, DEFAULT_PASTE_MODE),
            "restore_clipboard_after_paste": bool(restore_clipboard_after_paste),
        }
        self.save(data)

    def load_progress(self, path: str | Path) -> FileProgress:
        data = self.load()
        settings = self.load_settings()
        item = data.get("files", {}).get(self._normalize_path(path), {})

        next_index = item.get("next_index", 0)
        comment_style = item.get("comment_style", DEFAULT_COMMENT_STYLE)
        output_mode = item.get("output_mode", settings["default_output_mode"])
        smart_chunk_length = item.get(
            "smart_chunk_length",
            settings["default_smart_chunk_length"],
        )
        paste_mode = item.get("paste_mode", settings["default_paste_mode"])

        if comment_style not in {"//", "#"}:
            comment_style = DEFAULT_COMMENT_STYLE
        if output_mode not in {"paragraph", "smart"}:
            output_mode = str(settings["default_output_mode"])
        if not isinstance(next_index, int) or next_index < 0:
            next_index = 0

        return FileProgress(
            next_index=next_index,
            comment_style=comment_style,
            output_mode=output_mode,
            smart_chunk_length=validate_smart_chunk_length(
                _coerce_int(smart_chunk_length, DEFAULT_SMART_CHUNK_LENGTH)
            ),
            paste_mode=_coerce_paste_mode(paste_mode, str(settings["default_paste_mode"])),
        )

    def save_progress(
        self,
        path: str | Path,
        next_index: int,
        comment_style: str,
        output_mode: str,
        smart_chunk_length: int,
        paste_mode: str,
    ) -> None:
        data = self.load()
        files = data.setdefault("files", {})
        files[self._normalize_path(path)] = {
            "next_index": max(0, int(next_index)),
            "comment_style": comment_style if comment_style in {"//", "#"} else DEFAULT_COMMENT_STYLE,
            "output_mode": output_mode if output_mode in {"paragraph", "smart"} else DEFAULT_OUTPUT_MODE,
            "smart_chunk_length": validate_smart_chunk_length(smart_chunk_length),
            "paste_mode": _coerce_paste_mode(paste_mode, DEFAULT_PASTE_MODE),
        }
        self.save(data)

    @staticmethod
    def _normalize_path(path: str | Path) -> str:
        return os.path.normcase(os.path.abspath(str(path)))


def _default_state() -> dict:
    return {
        "recent_file": None,
        "recent_files": [],
        "files": {},
        "hotkeys": {},
        "settings": {
            "default_output_mode": DEFAULT_OUTPUT_MODE,
            "default_smart_chunk_length": DEFAULT_SMART_CHUNK_LENGTH,
            "default_paste_mode": DEFAULT_PASTE_MODE,
            "restore_clipboard_after_paste": False,
        },
    }


def _coerce_int(value: object, fallback: int) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _coerce_paste_mode(value: object, fallback: str) -> str:
    if value in {"browse", "accumulate"}:
        return str(value)
    return fallback


def _updated_recent_files(value: object, path: str | Path, limit: int = 12) -> list[str]:
    normalized_path = str(Path(path))
    existing = value if isinstance(value, list) else []
    result = [normalized_path]
    for item in existing:
        item_path = str(item)
        if item_path and os.path.normcase(os.path.abspath(item_path)) != os.path.normcase(os.path.abspath(normalized_path)):
            result.append(item_path)
        if len(result) >= limit:
            break
    return result
