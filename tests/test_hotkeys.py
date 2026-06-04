from __future__ import annotations

import unittest

from app.hotkeys import (
    TRIGGER_KIND_MOUSE,
    build_hotkey_specs,
    default_hotkey_specs,
    find_duplicate_hotkeys,
    find_hotkey_warnings,
    format_mouse_display,
)
from app.models import HotkeySpec


class HotkeyHelpersTests(unittest.TestCase):
    def test_build_hotkey_specs_uses_saved_values(self) -> None:
        specs = build_hotkey_specs(
            {
                "next": {
                    "trigger_kind": "keyboard",
                    "modifiers": 0x0002,
                    "virtual_key": 0x41,
                    "display": "Ctrl+A",
                }
            }
        )
        self.assertEqual(specs[0].display, "Ctrl+A")
        self.assertEqual(specs[0].virtual_key, 0x41)
        self.assertEqual(specs[0].trigger_kind, "keyboard")

    def test_build_hotkey_specs_supports_mouse_trigger(self) -> None:
        specs = build_hotkey_specs(
            {
                "next": {
                    "trigger_kind": "mouse",
                    "modifiers": 0,
                    "virtual_key": 1,
                    "display": format_mouse_display(0, 1),
                }
            }
        )
        self.assertEqual(specs[0].trigger_kind, TRIGGER_KIND_MOUSE)
        self.assertEqual(specs[0].virtual_key, 1)

    def test_build_hotkey_specs_labels_saved_numpad_key(self) -> None:
        specs = build_hotkey_specs(
            {
                "next": {
                    "trigger_kind": "keyboard",
                    "modifiers": 0x0002,
                    "virtual_key": 0x61,
                    "display": "Ctrl+1",
                }
            }
        )
        self.assertEqual(specs[0].display, "Ctrl+Num 1")

    def test_duplicate_detection_returns_user_facing_message(self) -> None:
        specs = default_hotkey_specs()
        duplicated = HotkeySpec(
            action=specs[1].action,
            name=specs[1].name,
            hotkey_id=specs[1].hotkey_id,
            trigger_kind=specs[0].trigger_kind,
            modifiers=specs[0].modifiers,
            virtual_key=specs[0].virtual_key,
            display=specs[0].display,
        )
        collisions = find_duplicate_hotkeys([specs[0], duplicated, specs[2]])
        self.assertEqual(len(collisions), 1)
        self.assertIn(specs[0].display, collisions[0])

    def test_hotkey_warnings_flag_common_editor_shortcuts(self) -> None:
        specs = default_hotkey_specs()
        risky = HotkeySpec(
            action=specs[0].action,
            name=specs[0].name,
            hotkey_id=specs[0].hotkey_id,
            trigger_kind="keyboard",
            modifiers=0x0002,
            virtual_key=0x56,
            display="Ctrl+V",
        )

        warnings = find_hotkey_warnings([risky, specs[1], specs[2]])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Ctrl+V", warnings[0])


if __name__ == "__main__":
    unittest.main()
