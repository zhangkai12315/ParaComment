from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.hotkeys import default_hotkey_specs
from app.services.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_progress_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.json")
            file_path = Path(temp_dir) / "book.txt"
            store.save_progress(file_path, 5, "#", "smart", 160, "browse")
            progress = store.load_progress(file_path)
            self.assertEqual(progress.next_index, 5)
            self.assertEqual(progress.comment_style, "#")
            self.assertEqual(progress.output_mode, "smart")
            self.assertEqual(progress.smart_chunk_length, 160)
            self.assertEqual(progress.paste_mode, "browse")

    def test_recent_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.json")
            file_path = Path(temp_dir) / "book.txt"
            store.set_recent_file(file_path)
            recent = store.get_recent_file()
            self.assertEqual(recent, file_path)

    def test_recent_files_keep_latest_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.json")
            first = Path(temp_dir) / "first.txt"
            second = Path(temp_dir) / "second.txt"
            store.set_recent_file(first)
            store.set_recent_file(second)
            store.set_recent_file(first)

            self.assertEqual(store.get_recent_files(), [first, second])

    def test_hotkeys_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.json")
            specs = default_hotkey_specs()
            store.save_hotkeys(specs)
            hotkeys = store.load_hotkeys()
            self.assertEqual(hotkeys["next"]["trigger_kind"], "keyboard")
            self.assertEqual(hotkeys["next"]["display"], "Ctrl+Alt+Right")
            self.assertEqual(hotkeys["undo"]["virtual_key"], 0x08)

    def test_settings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.json")
            store.save_settings("smart", 180, "accumulate", True)
            settings = store.load_settings()
            self.assertEqual(settings["default_output_mode"], "smart")
            self.assertEqual(settings["default_smart_chunk_length"], 180)
            self.assertEqual(settings["default_paste_mode"], "accumulate")
            self.assertTrue(settings["restore_clipboard_after_paste"])


if __name__ == "__main__":
    unittest.main()
