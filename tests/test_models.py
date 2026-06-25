from __future__ import annotations

import unittest

from app.models import PasteOutcome


class PasteOutcomeTests(unittest.TestCase):
    def test_normal_paste_succeeds_when_text_is_inserted(self) -> None:
        outcome = PasteOutcome(inserted=True)
        self.assertTrue(outcome.fully_succeeded)

    def test_replace_is_partial_when_previous_text_was_not_removed(self) -> None:
        outcome = PasteOutcome(inserted=True, previous_removed=False)
        self.assertFalse(outcome.fully_succeeded)

    def test_failed_insert_is_not_successful(self) -> None:
        outcome = PasteOutcome(inserted=False, previous_removed=True)
        self.assertFalse(outcome.fully_succeeded)


if __name__ == "__main__":
    unittest.main()
