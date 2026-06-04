"""Application configuration constants."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ParaComment"
DEFAULT_COMMENT_STYLE = "//"
DEFAULT_OUTPUT_MODE = "smart"
DEFAULT_SMART_CHUNK_LENGTH = 120
DEFAULT_PASTE_MODE = "browse"

HOTKEY_IDS = {
    "next": 1,
    "previous": 2,
    "undo": 3,
}

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004

VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_BACK = 0x08

DEFAULT_HOTKEYS = {
    "next": {
        "name": "下一段并粘贴",
        "modifiers": MOD_CONTROL | MOD_ALT,
        "virtual_key": VK_RIGHT,
        "display": "Ctrl+Alt+Right",
    },
    "previous": {
        "name": "上一段",
        "modifiers": MOD_CONTROL | MOD_ALT,
        "virtual_key": VK_LEFT,
        "display": "Ctrl+Alt+Left",
    },
    "undo": {
        "name": "撤销上一次工具粘贴",
        "modifiers": MOD_CONTROL | MOD_ALT,
        "virtual_key": VK_BACK,
        "display": "Ctrl+Alt+Backspace",
    },
}


def get_state_file_path() -> Path:
    """Return the per-user application state path."""
    return get_app_data_dir() / "state.json"


def get_debug_log_path() -> Path:
    """Return the per-user debug log path."""
    return get_app_data_dir() / "logs" / "debug.log"


def get_app_data_dir() -> Path:
    """Return the per-user application data directory."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / "AppData" / "Roaming"
    return root / APP_NAME
