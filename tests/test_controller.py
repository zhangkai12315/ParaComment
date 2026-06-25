from __future__ import annotations

import unittest
from pathlib import Path

from app.main import ParaCommentController
from app.models import LoadedText, PasteOutcome, SessionState
from app.services.text_loader import build_output_units


class _LoggerStub:
    def log(self, event: str, **fields: object) -> None:
        pass


class _PasteServiceStub:
    def __init__(self, outcome: PasteOutcome) -> None:
        self.outcome = outcome

    def paste_text(self, text: str) -> PasteOutcome:
        return self.outcome


class ControllerStateTests(unittest.TestCase):
    def test_failed_paste_does_not_advance_session(self) -> None:
        controller = ParaCommentController.__new__(ParaCommentController)
        controller.debug_logger = _LoggerStub()
        controller.paste_service = _PasteServiceStub(PasteOutcome(inserted=False))
        controller.session = SessionState(
            document=LoadedText(Path("book.txt"), "utf-8", ["first"]),
            output_units=build_output_units(["first"], "paragraph", 120),
            paste_mode="accumulate",
        )

        outcome = controller._paste_index(0)

        self.assertFalse(outcome.inserted)
        self.assertEqual(controller.session.next_index, 0)
        self.assertEqual(controller.session.paste_history, [])

    def test_rebuilding_units_clears_stale_paste_history(self) -> None:
        paragraph = "第一句内容稍长一些。第二句内容也稍长一些。第三句继续补充内容。第四句作为结尾。"
        controller = ParaCommentController.__new__(ParaCommentController)
        controller.session = SessionState(
            document=LoadedText(Path("book.txt"), "utf-8", [paragraph]),
            output_units=build_output_units([paragraph], "smart", 20),
            next_index=1,
            output_mode="smart",
            smart_chunk_length=8,
            paste_mode="browse",
            paste_history=[0],
        )

        controller._rebuild_output_units(preserve_position=True)

        self.assertEqual(controller.session.paste_history, [])
        self.assertGreater(controller.session.total_units, 1)


if __name__ == "__main__":
    unittest.main()
