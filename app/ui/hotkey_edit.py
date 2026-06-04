"""A lightweight input for capturing global hotkey combinations."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QMouseEvent
from PySide6.QtWidgets import QLineEdit

from app.config import MOD_ALT, MOD_CONTROL, MOD_SHIFT
from app.hotkeys import (
    MOUSE_BUTTON_BACK,
    MOUSE_BUTTON_FORWARD,
    TRIGGER_KIND_KEYBOARD,
    TRIGGER_KIND_MOUSE,
    format_mouse_display,
)
from app.models import HotkeyTriggerKind

_MODIFIER_KEYS = {
    int(Qt.Key_Control),
    int(Qt.Key_Shift),
    int(Qt.Key_Alt),
    int(Qt.Key_Meta),
}

_MOUSE_BUTTON_MAP = {
    Qt.BackButton: MOUSE_BUTTON_BACK,
    Qt.ForwardButton: MOUSE_BUTTON_FORWARD,
}


class HotkeyEdit(QLineEdit):
    """Capture one global hotkey combination."""

    hotkey_changed = Signal()
    capture_started = Signal()
    capture_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._trigger_kind: HotkeyTriggerKind = TRIGGER_KIND_KEYBOARD
        self._modifiers = 0
        self._virtual_key = 0
        self._display = ""
        self.setObjectName("HotkeyEditor")
        self.setReadOnly(True)
        self.setPlaceholderText("点击后直接按下新的组合键或鼠标侧键")
        self.setMinimumWidth(220)
        self.setFixedHeight(40)

    def set_hotkey(
        self,
        trigger_kind: HotkeyTriggerKind,
        modifiers: int,
        virtual_key: int,
        display: str,
    ) -> None:
        """Set the current displayed hotkey value."""
        self._trigger_kind = trigger_kind
        self._modifiers = modifiers
        self._virtual_key = virtual_key
        self._display = display
        self.setText(display)

    def binding(self) -> tuple[HotkeyTriggerKind, int, int, str]:
        """Return the current hotkey binding tuple."""
        return self._trigger_kind, self._modifiers, self._virtual_key, self._display

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        key = int(event.key())

        if key in {int(Qt.Key_Tab), int(Qt.Key_Backtab)}:
            super().keyPressEvent(event)
            return

        if key == int(Qt.Key_Escape):
            self.clearFocus()
            event.accept()
            return

        if key in _MODIFIER_KEYS:
            event.accept()
            return

        qt_modifiers = self._filtered_modifiers(event.modifiers())
        virtual_key = int(event.nativeVirtualKey()) or self._qt_key_to_virtual_key(key)
        if virtual_key == 0:
            event.ignore()
            return

        display = self._build_keyboard_display(key, qt_modifiers, virtual_key)
        self.set_hotkey(
            TRIGGER_KIND_KEYBOARD,
            self._qt_to_win_modifiers(qt_modifiers),
            virtual_key,
            display,
        )
        self.hotkey_changed.emit()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        button_code = _MOUSE_BUTTON_MAP.get(event.button())
        if button_code is None:
            super().mousePressEvent(event)
            return

        qt_modifiers = self._filtered_modifiers(event.modifiers())
        win_modifiers = self._qt_to_win_modifiers(qt_modifiers)
        display = format_mouse_display(win_modifiers, button_code)
        self.set_hotkey(TRIGGER_KIND_MOUSE, win_modifiers, button_code, display)
        self.hotkey_changed.emit()
        event.accept()

    def focusInEvent(self, event) -> None:  # type: ignore[override]
        super().focusInEvent(event)
        self.selectAll()
        self.capture_started.emit()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        self.capture_finished.emit()

    @staticmethod
    def _filtered_modifiers(modifiers: Qt.KeyboardModifiers) -> Qt.KeyboardModifiers:
        allowed = Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier
        return modifiers & allowed

    @staticmethod
    def _qt_to_win_modifiers(modifiers: Qt.KeyboardModifiers) -> int:
        win_modifiers = 0
        if modifiers & Qt.ControlModifier:
            win_modifiers |= MOD_CONTROL
        if modifiers & Qt.AltModifier:
            win_modifiers |= MOD_ALT
        if modifiers & Qt.ShiftModifier:
            win_modifiers |= MOD_SHIFT
        return win_modifiers

    @staticmethod
    def _build_keyboard_display(key: int, modifiers: Qt.KeyboardModifiers, virtual_key: int | None = None) -> str:
        if virtual_key is not None:
            numpad_labels = {
                0x60: "Num 0",
                0x61: "Num 1",
                0x62: "Num 2",
                0x63: "Num 3",
                0x64: "Num 4",
                0x65: "Num 5",
                0x66: "Num 6",
                0x67: "Num 7",
                0x68: "Num 8",
                0x69: "Num 9",
            }
            label = numpad_labels.get(virtual_key)
            if label:
                prefix = []
                if modifiers & Qt.ControlModifier:
                    prefix.append("Ctrl")
                if modifiers & Qt.AltModifier:
                    prefix.append("Alt")
                if modifiers & Qt.ShiftModifier:
                    prefix.append("Shift")
                return "+".join([*prefix, label]) if prefix else label
        sequence = QKeySequence(modifiers.value | key)
        return sequence.toString(QKeySequence.NativeText)

    @staticmethod
    def _qt_key_to_virtual_key(key: int) -> int:
        if 0x30 <= key <= 0x39:
            return key
        if 0x41 <= key <= 0x5A:
            return key

        special_keys = {
            int(Qt.Key_Backspace): 0x08,
            int(Qt.Key_Tab): 0x09,
            int(Qt.Key_Return): 0x0D,
            int(Qt.Key_Enter): 0x0D,
            int(Qt.Key_Pause): 0x13,
            int(Qt.Key_CapsLock): 0x14,
            int(Qt.Key_Escape): 0x1B,
            int(Qt.Key_Space): 0x20,
            int(Qt.Key_PageUp): 0x21,
            int(Qt.Key_PageDown): 0x22,
            int(Qt.Key_End): 0x23,
            int(Qt.Key_Home): 0x24,
            int(Qt.Key_Left): 0x25,
            int(Qt.Key_Up): 0x26,
            int(Qt.Key_Right): 0x27,
            int(Qt.Key_Down): 0x28,
            int(Qt.Key_Insert): 0x2D,
            int(Qt.Key_Delete): 0x2E,
            int(Qt.Key_F1): 0x70,
            int(Qt.Key_F2): 0x71,
            int(Qt.Key_F3): 0x72,
            int(Qt.Key_F4): 0x73,
            int(Qt.Key_F5): 0x74,
            int(Qt.Key_F6): 0x75,
            int(Qt.Key_F7): 0x76,
            int(Qt.Key_F8): 0x77,
            int(Qt.Key_F9): 0x78,
            int(Qt.Key_F10): 0x79,
            int(Qt.Key_F11): 0x7A,
            int(Qt.Key_F12): 0x7B,
        }
        return special_keys.get(key, 0)
