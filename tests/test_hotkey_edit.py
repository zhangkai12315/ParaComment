from __future__ import annotations

import unittest

from PySide6.QtCore import Qt

from app.hotkeys import format_mouse_display
from app.ui.hotkey_edit import HotkeyEdit


class HotkeyEditTests(unittest.TestCase):
    def test_build_keyboard_display_accepts_keyboard_modifiers(self) -> None:
        display = HotkeyEdit._build_keyboard_display(
            int(Qt.Key_A),
            Qt.ControlModifier | Qt.AltModifier,
        )
        self.assertTrue(display)

    def test_mouse_display_formatter(self) -> None:
        display = format_mouse_display(0x0002, 1)
        self.assertEqual(display, "Ctrl+鼠标后退键")

    def test_build_keyboard_display_marks_numpad_keys(self) -> None:
        display = HotkeyEdit._build_keyboard_display(
            int(Qt.Key_1),
            Qt.ControlModifier,
            0x61,
        )
        self.assertEqual(display, "Ctrl+Num 1")


if __name__ == "__main__":
    unittest.main()
