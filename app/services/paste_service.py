"""Windows text output helpers for paste and undo."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication

from app.models import PasteOutcome
from app.services.debug_logger import DebugLogger

CTRL_V = 0x56
CTRL_Z = 0x5A
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
CLIPBOARD_SETTLE_SECONDS = 0.005
REPLACE_UNDO_SETTLE_SECONDS = 0.035
CLIPBOARD_RESTORE_DELAY_SECONDS = 0.08

user32 = ctypes.WinDLL("user32", use_last_error=True)
ULONG_PTR = wintypes.WPARAM


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUT_UNION(ctypes.Union):
    _fields_ = (
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    )


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = (
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    )


LPINPUT = ctypes.POINTER(INPUT)

user32.SendInput.argtypes = [wintypes.UINT, LPINPUT, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


class PasteService:
    """Paste formatted text into the active editor and undo via Ctrl+Z."""

    def __init__(self, logger: DebugLogger | None = None) -> None:
        self._logger = logger
        self._restore_clipboard_after_paste = False

    def set_restore_clipboard_after_paste(self, enabled: bool) -> None:
        self._restore_clipboard_after_paste = bool(enabled)

    def paste_text(self, text: str) -> PasteOutcome:
        foreground_before = self._foreground_window_snapshot()
        self._log(
            "paste.start",
            text_length=len(text),
            line_count=text.count("\n") + 1,
            foreground=foreground_before,
        )
        clipboard = QApplication.clipboard()
        previous_clipboard_data = (
            _clone_clipboard_data(clipboard.mimeData()) if self._restore_clipboard_after_paste else None
        )
        clipboard.setText(text)
        QApplication.processEvents()
        self._log("paste.clipboard.updated", text_length=len(text))
        time.sleep(CLIPBOARD_SETTLE_SECONDS)
        send_result = self._send_ctrl_combo(CTRL_V)
        self._restore_clipboard_if_needed(previous_clipboard_data)
        foreground_after = self._foreground_window_snapshot()
        inserted = self._send_succeeded(send_result)
        self._log("paste.completed", success=inserted, send_result=send_result, foreground=foreground_after)
        return PasteOutcome(inserted=inserted)

    def undo_last_paste(self) -> bool:
        self._log("paste.undo.start", foreground=self._foreground_window_snapshot())
        send_result = self._send_ctrl_combo(CTRL_Z)
        success = self._send_succeeded(send_result)
        self._log(
            "paste.undo.completed",
            success=success,
            send_result=send_result,
            foreground=self._foreground_window_snapshot(),
        )
        return success

    def replace_text(self, text: str) -> PasteOutcome:
        foreground_before = self._foreground_window_snapshot()
        self._log(
            "paste.replace.start",
            text_length=len(text),
            line_count=text.count("\n") + 1,
            foreground=foreground_before,
        )
        clipboard = QApplication.clipboard()
        previous_clipboard_data = (
            _clone_clipboard_data(clipboard.mimeData()) if self._restore_clipboard_after_paste else None
        )
        clipboard.setText(text)
        QApplication.processEvents()
        self._log("paste.clipboard.updated", text_length=len(text))
        time.sleep(CLIPBOARD_SETTLE_SECONDS)

        undo_result = self._send_ctrl_combo(CTRL_Z)
        QApplication.processEvents()
        time.sleep(REPLACE_UNDO_SETTLE_SECONDS)
        paste_result = self._send_ctrl_combo(CTRL_V)
        self._restore_clipboard_if_needed(previous_clipboard_data)
        previous_removed = self._send_succeeded(undo_result)
        inserted = self._send_succeeded(paste_result)

        self._log(
            "paste.replace.completed",
            success=inserted and previous_removed,
            inserted=inserted,
            previous_removed=previous_removed,
            undo_result=undo_result,
            paste_result=paste_result,
            foreground=self._foreground_window_snapshot(),
            foreground_before=foreground_before,
        )
        return PasteOutcome(inserted=inserted, previous_removed=previous_removed)

    def _send_ctrl_combo(self, vk_code: int) -> dict[str, object]:
        input_items = self._active_modifier_keyups()
        input_items.extend(
            [
                self._build_keyboard_input(VK_CONTROL, key_up=False),
                self._build_keyboard_input(vk_code, key_up=False),
                self._build_keyboard_input(vk_code, key_up=True),
                self._build_keyboard_input(VK_CONTROL, key_up=True),
            ]
        )
        inputs = (INPUT * len(input_items))(*input_items)

        ctypes.set_last_error(0)
        sent = int(user32.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT)))
        error_code = ctypes.get_last_error()
        result = {
            "vk_code": vk_code,
            "requested": len(inputs),
            "sent": sent,
            "error_code": error_code,
            "input_size": ctypes.sizeof(INPUT),
        }
        self._log("paste.send_input_batch", **result)
        return result

    @staticmethod
    def _build_keyboard_input(vk_code: int, key_up: bool) -> INPUT:
        keyboard = KEYBDINPUT(
            wVk=vk_code,
            wScan=0,
            dwFlags=KEYEVENTF_KEYUP if key_up else 0,
            time=0,
            dwExtraInfo=0,
        )
        event = INPUT(type=INPUT_KEYBOARD)
        event.ki = keyboard
        return event

    @staticmethod
    def _active_modifier_keyups() -> list[INPUT]:
        keyups: list[INPUT] = []
        for vk_code in (VK_MENU, VK_SHIFT, VK_CONTROL):
            if user32.GetAsyncKeyState(vk_code) & 0x8000:
                keyups.append(PasteService._build_keyboard_input(vk_code, key_up=True))
        return keyups

    def _restore_clipboard_if_needed(self, previous_data: QMimeData | None) -> None:
        if previous_data is None:
            return
        time.sleep(CLIPBOARD_RESTORE_DELAY_SECONDS)
        QApplication.clipboard().setMimeData(previous_data)
        QApplication.processEvents()
        self._log("paste.clipboard.restored", formats=previous_data.formats())

    def _log(self, event: str, **fields: object) -> None:
        if self._logger:
            self._logger.log(event, **fields)

    @staticmethod
    def _send_succeeded(result: dict[str, object]) -> bool:
        requested = result.get("requested")
        sent = result.get("sent")
        return isinstance(requested, int) and requested > 0 and sent == requested

    @staticmethod
    def _foreground_window_snapshot() -> dict[str, int | str]:
        hwnd = user32.GetForegroundWindow()
        return {
            "hwnd": int(hwnd or 0),
            "title": _read_window_text(hwnd),
            "class_name": _read_class_name(hwnd),
        }


def _read_window_text(hwnd: int | None) -> str:
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _read_class_name(hwnd: int | None) -> str:
    if not hwnd:
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    if user32.GetClassNameW(hwnd, buffer, len(buffer)) <= 0:
        return ""
    return buffer.value


def _clone_clipboard_data(source: QMimeData | None) -> QMimeData:
    clone = QMimeData()
    if source is None:
        return clone
    for data_format in source.formats():
        clone.setData(data_format, source.data(data_format))
    return clone
