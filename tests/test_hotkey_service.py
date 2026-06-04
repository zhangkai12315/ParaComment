from __future__ import annotations

import unittest

from app.models import HotkeySpec
from app.services.hotkey_service import HotkeyService


class HotkeyServiceTests(unittest.TestCase):
    def test_matching_keyboard_action_returns_expected_action(self) -> None:
        service = HotkeyService([])
        service._keyboard_specs = [
            HotkeySpec(
                action="next",
                name="涓嬩竴娈靛苟绮樿创",
                hotkey_id=1,
                trigger_kind="keyboard",
                modifiers=2,
                virtual_key=68,
                display="Ctrl+D",
            )
        ]
        self.assertEqual(service._matching_keyboard_action(68, 2), "next")
        self.assertIsNone(service._matching_keyboard_action(68, 0))

    def test_keyboard_action_is_pending_until_key_up(self) -> None:
        service = HotkeyService([])
        service._keyboard_specs = [
            HotkeySpec(
                action="previous",
                name="previous",
                hotkey_id=2,
                trigger_kind="keyboard",
                modifiers=0,
                virtual_key=65,
                display="A",
            )
        ]
        action = service._matching_keyboard_action(65, 0)
        self.assertEqual(action, "previous")
        service._pending_keyboard_actions[65] = action
        self.assertEqual(service._pending_keyboard_actions.pop(65), "previous")

    def test_matching_mouse_action_returns_expected_action(self) -> None:
        service = HotkeyService([])
        service._mouse_specs = [
            HotkeySpec(
                action="next",
                name="下一段并粘贴",
                hotkey_id=1,
                trigger_kind="mouse",
                modifiers=0,
                virtual_key=2,
                display="鼠标前进键",
            )
        ]
        self.assertEqual(service._matching_mouse_action(2, 0), "next")
        self.assertIsNone(service._matching_mouse_action(1, 0))

    def test_mouse_action_is_dispatched_on_button_up(self) -> None:
        service = HotkeyService([])
        service._mouse_specs = [
            HotkeySpec(
                action="next",
                name="下一段并粘贴",
                hotkey_id=1,
                trigger_kind="mouse",
                modifiers=0,
                virtual_key=2,
                display="鼠标前进键",
            )
        ]
        self.assertTrue(service._begin_mouse_action(2, 0))
        self.assertEqual(service._finish_mouse_action(2), "next")
        self.assertIsNone(service._finish_mouse_action(2))


if __name__ == "__main__":
    unittest.main()
